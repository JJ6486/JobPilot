"""Request and response bodies for the tracker API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.resume import ResumeContent
from app.db.models import Channel, Status


class AnalyzeRequest(BaseModel):
    jd_text: str = Field(min_length=20)
    source_portal: str = ""
    url: str = ""
    tailor_despite_blockers: bool = False
    use_cache: bool = True


class TaskCreated(BaseModel):
    task_id: str


class ApplicationSummary(BaseModel):
    id: int
    job_id: int
    status: str
    fit_score: int
    recommendation: str
    title: str
    company: str
    city: str
    source_portal: str
    url: str
    role_family: str
    channel: str
    applied_at: datetime | None
    follow_up_at: datetime | None
    follow_up_due: bool
    suggest_ghosted: bool
    created_at: datetime
    updated_at: datetime


class ApplicationList(BaseModel):
    items: list[ApplicationSummary]
    total: int
    page: int
    page_size: int
    follow_ups_due: int
    ghost_suggestions: int


class EventOut(BaseModel):
    id: int
    type: str
    from_status: str | None
    to_status: str | None
    note: str
    created_at: datetime


class JobOut(BaseModel):
    id: int
    title: str
    company: str
    city: str
    country: str
    source_portal: str
    url: str
    deadline: str
    salary_text: str
    employment_type: str
    role_family: str
    jd_text: str
    analysis: dict[str, Any]
    created_at: datetime


class ApplicationDetail(ApplicationSummary):
    job: JobOut
    fit: dict[str, Any]
    resume_variant: str
    resume: ResumeContent | None
    has_docx: bool
    has_pdf: bool
    pdf_note: str
    cover_letter: str
    email_subject: str
    email_body: str
    whatsapp_message: str
    warnings: list[dict[str, Any]]
    high_warnings: int
    warnings_confirmed: bool
    download_blocked: bool
    tailor_issues: list[str]
    duplicates: list[dict[str, Any]]
    skip_reason: str
    contact_name: str
    contact_info: str
    notes: str
    ghost_dismissed: bool
    events: list[EventOut]


class ApplicationPatch(BaseModel):
    resume: ResumeContent | None = None
    cover_letter: str | None = None
    email_subject: str | None = None
    email_body: str | None = None
    whatsapp_message: str | None = None
    channel: Channel | None = None
    contact_name: str | None = None
    contact_info: str | None = None
    notes: str | None = None
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    warnings_confirmed: bool | None = None
    ghost_dismissed: bool | None = None


class StatusChange(BaseModel):
    status: Status
    note: str = ""


class RegenerateRequest(BaseModel):
    target: Literal["resume", "cover_letter"]


class TruthBankDocument(BaseModel):
    yaml: str
    valid: bool
    problems: list[str] = []
    hash: str | None = None


class TruthBankUpdate(BaseModel):
    yaml: str
