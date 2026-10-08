"""Database operations shared by the pipeline, the API and the CLI."""

from datetime import datetime, timedelta

from sqlmodel import Session, col, select

from app.core.dedupe import JobRecord, canonical_url, job_key
from app.core.score import FitScore
from app.db.models import STATUSES, Application, Event, Job, JobRequirement, now

FOLLOW_UP_AFTER = timedelta(days=7)
GHOST_AFTER = timedelta(days=21)
REPLIED_STATUSES = {"replied", "interview", "offer", "rejected"}


def add_event(
    session: Session,
    application_id: int,
    type_: str,
    note: str = "",
    from_status: str | None = None,
    to_status: str | None = None,
) -> Event:
    event = Event(
        application_id=application_id,
        type=type_,
        note=note,
        from_status=from_status,
        to_status=to_status,
    )
    session.add(event)
    return event


def job_records(session: Session) -> list[JobRecord]:
    """Every saved job with its latest application's status, for duplicate detection."""
    rows = session.exec(
        select(Job, Application)
        .join(Application, col(Application.job_id) == col(Job.id))
        .order_by(col(Application.id))
    ).all()
    latest: dict[int, tuple[Job, Application]] = {}
    for job, app in rows:
        assert job.id is not None
        latest[job.id] = (job, app)
    return [
        JobRecord(
            id=str(app.id),
            company=job.company,
            title=job.title,
            city=job.city,
            url=job.url,
            jd_text=job.jd_text,
            status=app.status,
            applied_at=app.applied_at.isoformat() if app.applied_at else None,
            created_at=job.created_at.isoformat(),
        )
        for job, app in latest.values()
    ]


def new_job(**fields: object) -> Job:
    job = Job(**fields)  # type: ignore[arg-type]
    job.job_key = job_key(job.company, job.title, job.city)
    job.canonical_url = canonical_url(job.url)
    return job


def save_requirements(session: Session, job_id: int, fit: FitScore) -> None:
    for old in session.exec(select(JobRequirement).where(JobRequirement.job_id == job_id)).all():
        session.delete(old)
    for req in fit.requirements:
        session.add(
            JobRequirement(job_id=job_id, skill=req.requirement, kind=req.kind, result=req.result)
        )


def set_status(
    session: Session, app: Application, status: str, note: str = "", at: datetime | None = None
) -> None:
    """Change status and log it. Marking 'applied' stamps applied_at and a +7 day follow-up."""
    if status not in STATUSES:
        raise ValueError(f"Unknown status {status!r}. Use one of: {', '.join(STATUSES)}")
    if status == app.status:
        return
    moment = at or now()
    old = app.status
    app.status = status
    if status == "applied":
        app.applied_at = app.applied_at or moment
        app.follow_up_at = app.follow_up_at or app.applied_at + FOLLOW_UP_AFTER
    if status != "applied":
        app.ghost_dismissed = False
    app.updated_at = moment
    assert app.id is not None
    add_event(session, app.id, "status_change", note, from_status=old, to_status=status)


def follow_up_due(app: Application, at: datetime | None = None) -> bool:
    return (
        app.status == "applied"
        and app.follow_up_at is not None
        and app.follow_up_at <= (at or now())
    )


def suggest_ghosted(app: Application, at: datetime | None = None) -> bool:
    """Suggest (never apply) 'ghosted' ~21 days after applying with no reply."""
    return (
        app.status == "applied"
        and not app.ghost_dismissed
        and app.applied_at is not None
        and app.applied_at + GHOST_AFTER <= (at or now())
    )
