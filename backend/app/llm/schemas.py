"""Structured outputs the LLM must return. Kept flat and simple so every provider can follow them.

Call 1 (parse + judge) returns `AnalysisResult`; call 2 (tailor + letters) returns `TailorResult`.
The LLM never returns a score: `core/score.py` computes it from these judgements.
"""

from typing import Literal

from pydantic import BaseModel, Field

RoleFamilyOrOther = Literal["software_ict", "teaching", "other"]
MatchResult = Literal["matched", "adjacent", "missing"]
Fit = Literal["strong", "partial", "weak"]


# ---- Call 1: parse the JD and judge each requirement ------------------------------------


class ParsedJD(BaseModel):
    title: str
    company: str = ""
    city: str = ""
    country: str = ""
    employment_type: str = ""
    remote_allowed: bool = False
    role_family: RoleFamilyOrOther
    language: str = Field("en", description="Main language of the JD text, e.g. en, ar, mixed")
    must_have_skills: list[str] = []
    nice_to_have_skills: list[str] = []
    min_years_experience: float | None = None
    education_requirements: list[str] = []
    certification_requirements: list[str] = []
    hard_conditions: list[str] = Field(
        default=[],
        description="Non-negotiable conditions: nationality, visa/iqama, licence, gender, "
        "location, mandatory qualification, driving licence, etc.",
    )
    salary_text: str = ""
    deadline: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    contact_whatsapp: str = ""
    how_to_apply: str = ""


class RequirementJudgement(BaseModel):
    requirement: str
    kind: Literal["must", "nice"]
    result: MatchResult
    evidence_ids: list[str] = Field(
        default=[], description="Truth-bank ids (bullets, projects, skills' evidence) that prove it"
    )
    matched_skill: str = Field("", description="Truth-bank skill name this maps to, if any")
    note: str = ""


class HardConditionJudgement(BaseModel):
    condition: str
    category: Literal[
        "nationality", "visa", "gender", "location", "licence", "qualification", "other"
    ] = "other"
    status: Literal["met", "not_met", "unclear"]
    reason: str


class LogisticsJudgement(BaseModel):
    factor: Literal["location", "visa", "licence", "language", "schedule", "other"]
    status: Literal["ok", "concern", "blocker"]
    note: str


class AnalysisResult(BaseModel):
    jd: ParsedJD
    requirements: list[RequirementJudgement]
    relevant_years: float = Field(
        description="Candidate's years of experience relevant to this role"
    )
    experience_fit: Fit
    experience_note: str
    role_alignment: Fit
    role_alignment_note: str
    hard_conditions: list[HardConditionJudgement] = []
    logistics: list[LogisticsJudgement] = []
    red_flags: list[str] = []
    summary: list[str] = Field(description="Exactly three short lines summarising the fit")


# ---- Call 2: tailor the resume and write the letters ------------------------------------


class TailoredBullet(BaseModel):
    source_id: str = Field(description="Truth-bank bullet id this text comes from")
    text: str = Field(description="The bullet, optionally lightly reworded; same facts")


class TailoredEntry(BaseModel):
    source_id: str = Field(description="Truth-bank experience or project id")
    bullets: list[TailoredBullet]


class SkillGroup(BaseModel):
    label: str
    skills: list[str] = Field(description="Exact truth-bank skill names, most relevant first")


class TailorResult(BaseModel):
    headline: str = Field(
        "", description="Short target job title from the JD, e.g. IT Project Coordinator"
    )
    summary: str
    experience: list[TailoredEntry]
    projects: list[TailoredEntry] = []
    skill_groups: list[SkillGroup]
    workshop_ids: list[str] = []
    achievement_ids: list[str] = []
    certification_ids: list[str] = []
    currently_learning: list[str] = []
    cover_letter: str
    email_subject: str
    email_body: str
    whatsapp_message: str
