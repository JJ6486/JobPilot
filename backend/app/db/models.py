"""Tracker tables. JSON columns hold the structured pipeline outputs (analysis, fit, resume
content, validation) so the Review screen can show and edit them without re-running the LLM."""

from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel

Status = Literal[
    "saved", "tailored", "applied", "replied", "interview", "offer",
    "rejected", "ghosted", "skipped", "withdrawn",
]  # fmt: skip
STATUSES: tuple[str, ...] = Status.__args__  # type: ignore[attr-defined]
Channel = Literal["portal", "email", "whatsapp", "other"]
EventType = Literal["created", "status_change", "note", "edited", "regenerated", "reminder"]


def now() -> datetime:
    """Timezone-aware UTC; the frontend shows times in the user's local zone."""
    return datetime.now(UTC).replace(microsecond=0)


class Job(SQLModel, table=True):
    __tablename__ = "jobs"

    id: int | None = Field(default=None, primary_key=True)
    title: str
    company: str = ""
    city: str = ""
    country: str = ""
    source_portal: str = ""
    url: str = ""
    canonical_url: str = Field(default="", index=True)
    job_key: str = Field(default="", index=True)  # hash of (company, title, city)
    posted_date: str = ""
    deadline: str = ""
    salary_text: str = ""
    employment_type: str = ""
    role_family: str = ""
    jd_text: str  # full snapshot: postings disappear
    jd_hash: str = Field(index=True)
    parsed_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))  # analysis
    created_at: datetime = Field(default_factory=now)


class Application(SQLModel, table=True):
    __tablename__ = "applications"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    status: str = Field(default="saved", index=True)
    fit_score: int = 0
    recommendation: str = ""
    fit_breakdown_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    resume_variant: str = ""  # role family / template used
    resume_content_json: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    resume_docx_path: str | None = None
    resume_pdf_path: str | None = None
    pdf_note: str = ""
    cover_letter: str = ""
    email_subject: str = ""
    email_body: str = ""
    whatsapp_message: str = ""
    validation_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    warnings_confirmed: bool = False  # "I confirm this is true" for high-severity warnings
    tailor_issues_json: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    duplicates_json: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    skip_reason: str = ""
    channel: str = "portal"
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    ghost_dismissed: bool = False
    contact_name: str = ""
    contact_info: str = ""
    notes: str = ""
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: int | None = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="applications.id", index=True)
    type: str
    from_status: str | None = None
    to_status: str | None = None
    note: str = ""
    created_at: datetime = Field(default_factory=now)


class JobRequirement(SQLModel, table=True):
    __tablename__ = "job_requirements"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    skill: str
    kind: str  # must | nice
    result: str  # matched | adjacent | missing
