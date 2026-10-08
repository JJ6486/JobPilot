"""The stage-1 pipeline: parse -> dedupe -> score -> tailor -> letter -> save.

Two LLM calls at most (analyze, tailor), both cached. The job and application are saved to
SQLite right after scoring, so a later failure (e.g. a rate limit while tailoring) still keeps
the job in the tracker. Files go to `data/outputs/<application_id>/`.
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from sqlmodel import Session

from app.config import Settings
from app.core.cover_letter import CoverLetterBundle, bundle_from, personalize
from app.core.dedupe import DuplicateMatch, JobRecord, find_duplicates
from app.core.libreoffice import find_soffice
from app.core.parse_jd import analyze_jd
from app.core.render_docx import RenderError, convert_to_pdf, output_filename, render_docx
from app.core.resume import ResumeContent
from app.core.score import FitScore, compute_score
from app.core.tailor import build_resume, run_tailor
from app.core.truth_bank import RoleFamily, TruthBank
from app.core.validator import ValidationReport, Validator
from app.db.models import Application, Job, now
from app.db.repository import add_event, job_records, new_job, save_requirements, set_status
from app.llm.base import LLMProvider, StatusCallback
from app.llm.cache import LLMCache, text_hash
from app.llm.schemas import AnalysisResult, ParsedJD

Step = Literal["parse", "dedupe", "score", "tailor", "letter", "save"]
StepState = Literal["running", "done", "skipped", "info"]
ProgressCallback = Callable[[Step, StepState, str], None]
CHANNEL_BY_PORTAL = {"email": "email", "whatsapp": "whatsapp"}


class PipelineResult(BaseModel):
    application_id: int
    analysis: AnalysisResult
    fit: FitScore
    duplicates: list[DuplicateMatch]
    role_family: RoleFamily
    tailored: bool
    skip_reason: str = ""
    resume: ResumeContent | None = None
    letters: CoverLetterBundle | None = None
    validation: ValidationReport | None = None
    tailor_issues: list[str] = []
    resume_docx: str | None = None
    resume_pdf: str | None = None
    pdf_note: str = ""
    llm_calls_made: int = 0


def choose_role_family(analysis: AnalysisResult) -> RoleFamily:
    if analysis.jd.role_family == "other":
        teaching = re.search(r"teach|tutor|instructor|lecturer", analysis.jd.title, re.I)
        return "teaching" if teaching else "software_ict"
    return analysis.jd.role_family


def letters_of(app: Application) -> dict[str, str]:
    return {
        "cover_letter": app.cover_letter,
        "email_subject": app.email_subject,
        "email_body": app.email_body,
        "whatsapp_message": app.whatsapp_message,
    }


def validate(
    tb: TruthBank, jd: ParsedJD, resume: ResumeContent, letters: dict[str, str]
) -> ValidationReport:
    validator = Validator(tb, allowed_extra=[jd.company, jd.title, jd.city, jd.country])
    return validator.validate(resume, letters)


def render_files(app: Application, job: Job, tb: TruthBank, settings: Settings) -> None:
    """(Re-)render DOCX and, if LibreOffice is available, PDF, from the stored content. No LLM."""
    assert app.resume_content_json is not None and app.id is not None
    content = ResumeContent.model_validate(app.resume_content_json)
    template = settings.data_dir / "templates" / tb.role_families[content.role_family].template
    out_dir = settings.outputs_dir / str(app.id)
    docx = render_docx(
        content,
        tb,
        template,
        out_dir / output_filename(tb.profile.full_name, job.company or "Company", job.title),
    )
    app.resume_docx_path, app.resume_pdf_path, app.pdf_note = str(docx), None, ""
    soffice = find_soffice(settings.libreoffice_path)
    if soffice is None:
        app.pdf_note = "LibreOffice not found: DOCX only."
        return
    try:
        app.resume_pdf_path = str(convert_to_pdf(docx, soffice))
    except RenderError as exc:
        app.pdf_note = f"PDF export failed: {exc}"


def rerender(
    session: Session, app: Application, job: Job, tb: TruthBank, settings: Settings
) -> ValidationReport:
    """Re-validate and re-render the (possibly edited) stored content. Never calls the LLM."""
    assert app.resume_content_json is not None
    content = ResumeContent.model_validate(app.resume_content_json)
    report = validate(
        tb, AnalysisResult.model_validate(job.parsed_json).jd, content, letters_of(app)
    )
    app.validation_json = [w.model_dump() for w in report.warnings]
    render_files(app, job, tb, settings)
    app.updated_at = now()
    session.add(app)
    return report


def apply_tailoring(
    session: Session,
    app: Application,
    job: Job,
    tb: TruthBank,
    settings: Settings,
    provider: LLMProvider,
    cache: LLMCache,
    target: Literal["all", "resume", "cover_letter"] = "all",
    on_status: StatusCallback | None = None,
) -> tuple[bool, list[str]]:
    """Run LLM call 2 and store its result. Returns (from_cache, tailor issues)."""
    analysis = AnalysisResult.model_validate(job.parsed_json)
    role_family: RoleFamily = app.resume_variant  # type: ignore[assignment]
    tailor, cached = run_tailor(provider, analysis, tb, role_family, cache, job.jd_text, on_status)
    issues: list[str] = []
    if target in ("all", "resume"):
        resume, issues = build_resume(tailor, tb, role_family)
        app.resume_content_json = resume.model_dump()
        app.tailor_issues_json = issues
    if target in ("all", "cover_letter"):
        letters = personalize(bundle_from(tailor), tb.profile.full_name)
        app.cover_letter, app.email_subject = letters.cover_letter, letters.email_subject
        app.email_body, app.whatsapp_message = letters.email_body, letters.whatsapp_message
    app.warnings_confirmed = False  # new text needs a fresh check
    rerender(session, app, job, tb, settings)
    return cached, issues


def run_pipeline(
    jd_text: str,
    *,
    tb: TruthBank,
    provider: LLMProvider,
    settings: Settings,
    session: Session,
    source_portal: str = "",
    url: str = "",
    use_cache: bool = True,
    tailor_despite_blockers: bool = False,
    on_progress: ProgressCallback | None = None,
    on_status: StatusCallback | None = None,
) -> PipelineResult:
    progress = on_progress or (lambda *_: None)
    if not jd_text.strip():
        raise ValueError("The job description is empty.")
    cache = LLMCache(settings.data_dir / "cache", enabled=use_cache)
    calls = 0

    progress("parse", "running", "Reading the job description")
    analysis, cached = analyze_jd(provider, jd_text, tb, cache, on_status)
    calls += 0 if cached else 1
    jd = analysis.jd
    progress(
        "parse",
        "done",
        f"{jd.title} at {jd.company or 'unknown company'}" + (" (cached)" if cached else ""),
    )

    progress("dedupe", "running", "Checking saved jobs")
    probe = JobRecord(
        id="new", company=jd.company, title=jd.title, city=jd.city, url=url, jd_text=jd_text
    )
    duplicates = find_duplicates(probe, job_records(session))
    progress(
        "dedupe",
        "done",
        f"{len(duplicates)} possible duplicate(s)" if duplicates else "No duplicates",
    )

    progress("score", "running", "Scoring fit")
    fit = compute_score(analysis, tb, jd_text)
    progress("score", "done", f"{fit.score}/100, {fit.recommendation}")

    role_family = choose_role_family(analysis)
    job = new_job(
        title=jd.title,
        company=jd.company,
        city=jd.city,
        country=jd.country,
        source_portal=source_portal,
        url=url,
        deadline=jd.deadline,
        salary_text=jd.salary_text,
        employment_type=jd.employment_type,
        role_family=role_family,
        jd_text=jd_text,
        jd_hash=text_hash(jd_text),
        parsed_json=analysis.model_dump(mode="json"),
    )
    session.add(job)
    session.flush()
    assert job.id is not None
    contact = ", ".join(c for c in (jd.contact_email, jd.contact_phone, jd.contact_whatsapp) if c)
    app = Application(
        job_id=job.id,
        status="saved",
        fit_score=fit.score,
        recommendation=fit.recommendation,
        fit_breakdown_json=fit.model_dump(mode="json"),
        resume_variant=role_family,
        duplicates_json=[d.model_dump(mode="json") for d in duplicates],
        channel=CHANNEL_BY_PORTAL.get(source_portal.strip().lower(), "portal"),
        contact_info=contact,
    )
    session.add(app)
    session.flush()
    assert app.id is not None
    add_event(session, app.id, "created", f"Analysed: {fit.score}/100, {fit.recommendation}")
    save_requirements(session, job.id, fit)
    session.commit()  # keep the job even if tailoring fails below

    result = PipelineResult(
        application_id=app.id,
        analysis=analysis,
        fit=fit,
        duplicates=duplicates,
        role_family=role_family,
        tailored=False,
    )
    if fit.blockers and not tailor_despite_blockers:
        app.skip_reason = result.skip_reason = "Hard blocker: " + "; ".join(fit.blockers)
        progress(
            "tailor", "skipped", "Hard blocker found, so no resume was generated (saves API quota)"
        )
        progress("letter", "skipped", "")
    else:
        progress("tailor", "running", f"Tailoring the {role_family} resume")
        cached, issues = apply_tailoring(
            session, app, job, tb, settings, provider, cache, on_status=on_status
        )
        calls += 0 if cached else 1
        set_status(session, app, "tailored")
        progress(
            "tailor",
            "done",
            Path(app.resume_docx_path or "").name + (" (cached)" if cached else ""),
        )
        high = sum(1 for w in app.validation_json if w["severity"] == "high")
        progress(
            "letter",
            "done",
            f"{high} high-severity warning(s)" if high else "No high-severity warnings",
        )
        result.tailored, result.tailor_issues = True, issues
        result.resume = ResumeContent.model_validate(app.resume_content_json)
        result.letters = CoverLetterBundle(**letters_of(app))
        result.validation = ValidationReport.model_validate({"warnings": app.validation_json})
        result.resume_docx, result.resume_pdf, result.pdf_note = (
            app.resume_docx_path,
            app.resume_pdf_path,
            app.pdf_note,
        )

    progress("save", "running", "Saving")
    session.add(app)
    session.commit()
    result.llm_calls_made = calls
    progress("save", "done", f"Application #{app.id}")
    return result
