"""Tracker API: list, detail, edit, status, re-render, regenerate, download, export, delete."""

import csv
import io
import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session, col, func, or_, select

from app.api.deps import ProviderDep, RegistryDep, SettingsDep, TruthBankDep
from app.api.schemas import (
    ApplicationDetail,
    ApplicationList,
    ApplicationPatch,
    ApplicationSummary,
    EventOut,
    JobOut,
    RegenerateRequest,
    StatusChange,
    TaskCreated,
)
from app.core.pipeline import apply_tailoring, letters_of, rerender, validate
from app.core.resume import ResumeContent
from app.db.models import Application, Event, Job, JobRequirement, now
from app.db.repository import add_event, follow_up_due, set_status, suggest_ghosted
from app.db.session import SessionDep, get_engine
from app.llm.cache import LLMCache
from app.llm.schemas import AnalysisResult
from app.tasks import TaskReporter

router = APIRouter(prefix="/applications", tags=["applications"])

SortField = Literal["created_at", "updated_at", "fit_score", "applied_at", "company", "status"]
LETTER_FIELDS = ("cover_letter", "email_subject", "email_body", "whatsapp_message")


# ---- helpers ----------------------------------------------------------------------------


def _get(session: Session, application_id: int) -> tuple[Application, Job]:
    app = session.get(Application, application_id)
    if app is None:
        raise HTTPException(404, f"Application {application_id} not found")
    job = session.get(Job, app.job_id)
    assert job is not None
    return app, job


def _summary(app: Application, job: Job) -> ApplicationSummary:
    assert app.id is not None and job.id is not None
    return ApplicationSummary(
        id=app.id,
        job_id=job.id,
        status=app.status,
        fit_score=app.fit_score,
        recommendation=app.recommendation,
        title=job.title,
        company=job.company,
        city=job.city,
        source_portal=job.source_portal,
        url=job.url,
        role_family=job.role_family,
        channel=app.channel,
        applied_at=app.applied_at,
        follow_up_at=app.follow_up_at,
        follow_up_due=follow_up_due(app),
        suggest_ghosted=suggest_ghosted(app),
        created_at=app.created_at,
        updated_at=app.updated_at,
    )


def _high(app: Application) -> int:
    return sum(1 for w in app.validation_json if w.get("severity") == "high")


def _detail(session: Session, app: Application, job: Job) -> ApplicationDetail:
    assert job.id is not None
    events = session.exec(
        select(Event)
        .where(Event.application_id == app.id)
        .order_by(col(Event.created_at), col(Event.id))
    ).all()
    high = _high(app)
    return ApplicationDetail(
        **_summary(app, job).model_dump(),
        job=JobOut(
            id=job.id,
            title=job.title,
            company=job.company,
            city=job.city,
            country=job.country,
            source_portal=job.source_portal,
            url=job.url,
            deadline=job.deadline,
            salary_text=job.salary_text,
            employment_type=job.employment_type,
            role_family=job.role_family,
            jd_text=job.jd_text,
            analysis=job.parsed_json,
            created_at=job.created_at,
        ),
        fit=app.fit_breakdown_json,
        resume_variant=app.resume_variant,
        resume=ResumeContent.model_validate(app.resume_content_json)
        if app.resume_content_json
        else None,
        has_docx=bool(app.resume_docx_path and Path(app.resume_docx_path).is_file()),
        has_pdf=bool(app.resume_pdf_path and Path(app.resume_pdf_path).is_file()),
        pdf_note=app.pdf_note,
        **letters_of(app),
        warnings=app.validation_json,
        high_warnings=high,
        warnings_confirmed=app.warnings_confirmed,
        download_blocked=high > 0 and not app.warnings_confirmed,
        tailor_issues=app.tailor_issues_json,
        duplicates=app.duplicates_json,
        skip_reason=app.skip_reason,
        contact_name=app.contact_name,
        contact_info=app.contact_info,
        notes=app.notes,
        ghost_dismissed=app.ghost_dismissed,
        events=[EventOut.model_validate(e, from_attributes=True) for e in events],
    )


def _filtered(
    status: str | None,
    portal: str | None,
    role_family: str | None,
    channel: str | None,
    score_min: int | None,
    score_max: int | None,
    date_from: datetime | None,
    date_to: datetime | None,
    q: str | None,
):  # type: ignore[no-untyped-def]
    stmt = select(Application, Job).join(Job, col(Job.id) == col(Application.job_id))
    if status:
        stmt = stmt.where(col(Application.status).in_(status.split(",")))
    if portal:
        stmt = stmt.where(func.lower(Job.source_portal) == portal.lower())
    if role_family:
        stmt = stmt.where(Job.role_family == role_family)
    if channel:
        stmt = stmt.where(Application.channel == channel)
    if score_min is not None:
        stmt = stmt.where(Application.fit_score >= score_min)
    if score_max is not None:
        stmt = stmt.where(Application.fit_score <= score_max)
    if date_from is not None:
        stmt = stmt.where(Application.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Application.created_at <= date_to)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Job.company).like(like),
                func.lower(Job.title).like(like),
                func.lower(Application.notes).like(like),
            )
        )
    return stmt


_SORT_COLUMNS = {
    "created_at": col(Application.created_at),
    "updated_at": col(Application.updated_at),
    "fit_score": col(Application.fit_score),
    "applied_at": col(Application.applied_at),
    "company": col(Job.company),
    "status": col(Application.status),
}


class Filters:
    """Shared query parameters for the list and the CSV export."""

    def __init__(
        self,
        status: Annotated[str | None, Query(description="Comma-separated statuses")] = None,
        portal: str | None = None,
        role_family: str | None = None,
        channel: str | None = None,
        score_min: int | None = None,
        score_max: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        q: Annotated[str | None, Query(description="Search company, title, notes")] = None,
        sort: SortField = "created_at",
        order: Literal["asc", "desc"] = "desc",
    ) -> None:
        self.stmt = _filtered(
            status, portal, role_family, channel, score_min, score_max, date_from, date_to, q
        )
        column = _SORT_COLUMNS[sort]
        self.order_by = (
            column.asc() if order == "asc" else column.desc(),
            col(Application.id).desc(),
        )


FiltersDep = Annotated[Filters, Depends()]


# ---- list / export ----------------------------------------------------------------------


@router.get("", response_model=ApplicationList)
def list_applications(
    session: SessionDep,
    filters: FiltersDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
) -> ApplicationList:
    rows = session.exec(filters.stmt.order_by(*filters.order_by)).all()
    summaries = [_summary(app, job) for app, job in rows]
    everything = session.exec(select(Application)).all()
    start = (page - 1) * page_size
    return ApplicationList(
        items=summaries[start : start + page_size],
        total=len(summaries),
        page=page,
        page_size=page_size,
        follow_ups_due=sum(1 for a in everything if follow_up_due(a)),
        ghost_suggestions=sum(1 for a in everything if suggest_ghosted(a)),
    )


@router.get("/export.csv")
def export_csv(session: SessionDep, filters: FiltersDep) -> StreamingResponse:
    rows = session.exec(filters.stmt.order_by(*filters.order_by)).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "created_at",
            "status",
            "fit_score",
            "recommendation",
            "company",
            "title",
            "city",
            "portal",
            "channel",
            "role_family",
            "applied_at",
            "follow_up_at",
            "contact_name",
            "contact_info",
            "url",
            "notes",
        ]
    )
    for app, job in rows:
        writer.writerow(
            [
                app.id,
                app.created_at.isoformat(),
                app.status,
                app.fit_score,
                app.recommendation,
                job.company,
                job.title,
                job.city,
                job.source_portal,
                app.channel,
                job.role_family,
                app.applied_at.isoformat() if app.applied_at else "",
                app.follow_up_at.isoformat() if app.follow_up_at else "",
                app.contact_name,
                app.contact_info,
                job.url,
                app.notes,
            ]
        )
    data = "﻿" + buf.getvalue()  # BOM so Excel opens UTF-8 (Arabic) correctly
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="jobpilot_applications.csv"'},
    )


# ---- detail / edit ----------------------------------------------------------------------


@router.get("/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: int, session: SessionDep) -> ApplicationDetail:
    app, job = _get(session, application_id)
    return _detail(session, app, job)


@router.patch("/{application_id}", response_model=ApplicationDetail)
def update_application(
    application_id: int, body: ApplicationPatch, session: SessionDep, tb: TruthBankDep
) -> ApplicationDetail:
    """Save edits. Edited resume/letter text is re-validated immediately (no LLM); call
    /rerender to rebuild the DOCX/PDF from it."""
    app, job = _get(session, application_id)
    changes = body.model_dump(exclude_unset=True)
    content_changed = False
    if "resume" in changes and body.resume is not None:
        if body.resume.role_family != app.resume_variant:
            raise HTTPException(422, "resume.role_family can't change; regenerate instead")
        app.resume_content_json = body.resume.model_dump()
        content_changed = True
    for field in LETTER_FIELDS:
        if field in changes:
            setattr(app, field, changes[field] or "")
            content_changed = True
    for field in (
        "channel",
        "contact_name",
        "contact_info",
        "applied_at",
        "follow_up_at",
        "ghost_dismissed",
    ):
        if field in changes:
            setattr(app, field, changes[field])
    if "notes" in changes and (changes["notes"] or "") != app.notes:
        app.notes = changes["notes"] or ""
        add_event(session, application_id, "note", app.notes[:500])

    if content_changed and app.resume_content_json:
        content = ResumeContent.model_validate(app.resume_content_json)
        report = validate(
            tb, AnalysisResult.model_validate(job.parsed_json).jd, content, letters_of(app)
        )
        app.validation_json = [w.model_dump() for w in report.warnings]
        app.warnings_confirmed = False
    if "warnings_confirmed" in changes:  # explicit confirmation wins (after any re-validation)
        app.warnings_confirmed = bool(changes["warnings_confirmed"])
        if app.warnings_confirmed:
            add_event(session, application_id, "note", "Confirmed flagged text is true")

    edited = [f for f in changes if f not in ("notes", "warnings_confirmed")]
    if edited:
        add_event(session, application_id, "edited", "Edited: " + ", ".join(edited))
    app.updated_at = now()
    session.add(app)
    session.commit()
    session.refresh(app)
    return _detail(session, app, job)


@router.post("/{application_id}/status", response_model=ApplicationDetail)
def change_status(
    application_id: int, body: StatusChange, session: SessionDep
) -> ApplicationDetail:
    app, job = _get(session, application_id)
    set_status(session, app, body.status, body.note)
    session.add(app)
    session.commit()
    session.refresh(app)
    return _detail(session, app, job)


@router.post("/{application_id}/rerender", response_model=ApplicationDetail)
def rerender_application(
    application_id: int, session: SessionDep, settings: SettingsDep, tb: TruthBankDep
) -> ApplicationDetail:
    app, job = _get(session, application_id)
    if not app.resume_content_json:
        raise HTTPException(409, "This application has no resume yet; regenerate it first")
    rerender(session, app, job, tb, settings)
    add_event(session, application_id, "edited", "Re-rendered resume files")
    session.commit()
    session.refresh(app)
    return _detail(session, app, job)


@router.post("/{application_id}/regenerate", response_model=TaskCreated, status_code=202)
def regenerate(
    application_id: int,
    body: RegenerateRequest,
    session: SessionDep,
    settings: SettingsDep,
    tb: TruthBankDep,
    provider: ProviderDep,
    registry: RegistryDep,
) -> TaskCreated:
    """Ask the LLM again (cache bypassed). Runs in the background like /analyze."""
    _get(session, application_id)

    def work(report: TaskReporter) -> int:
        report.set_application(application_id)
        report.step("tailor", "running", f"Regenerating the {body.target.replace('_', ' ')}")
        with Session(get_engine(settings)) as s:
            app, job = _get(s, application_id)
            cache = LLMCache(settings.data_dir / "cache", enabled=False)
            apply_tailoring(
                s,
                app,
                job,
                tb,
                settings,
                provider,
                cache,
                target=body.target,
                on_status=report.message,
            )
            if app.status == "saved":
                set_status(s, app, "tailored")
            add_event(
                s, application_id, "regenerated", f"Regenerated {body.target.replace('_', ' ')}"
            )
            s.add(app)
            s.commit()
        report.step("tailor", "done", "Done")
        return application_id

    return TaskCreated(task_id=registry.submit("regenerate", work).id)


@router.get("/{application_id}/resume.{fmt}")
def download_resume(
    application_id: int, fmt: Literal["docx", "pdf"], session: SessionDep
) -> FileResponse:
    app, _job = _get(session, application_id)
    if _high(app) and not app.warnings_confirmed:
        raise HTTPException(
            409, "High-severity warnings: fix the text or confirm it's true before downloading"
        )
    path = app.resume_docx_path if fmt == "docx" else app.resume_pdf_path
    if not path or not Path(path).is_file():
        raise HTTPException(
            404, app.pdf_note if fmt == "pdf" and app.pdf_note else f"No {fmt.upper()} file yet"
        )
    media = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if fmt == "docx"
        else "application/pdf"
    )
    return FileResponse(path, media_type=media, filename=Path(path).name)


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: int, session: SessionDep, settings: SettingsDep) -> None:
    """Delete an application, its timeline and files (and its job, if nothing else uses it)."""
    app, job = _get(session, application_id)
    for event in session.exec(select(Event).where(Event.application_id == application_id)).all():
        session.delete(event)
    session.flush()  # events first: no ORM relationships to order the deletes
    session.delete(app)
    session.flush()
    others = session.exec(select(Application).where(Application.job_id == job.id)).first()
    if others is None:
        for req in session.exec(
            select(JobRequirement).where(JobRequirement.job_id == job.id)
        ).all():
            session.delete(req)
        session.flush()
        session.delete(job)
    session.commit()
    shutil.rmtree(settings.outputs_dir / str(application_id), ignore_errors=True)
