"""Shared test fixtures: a fake truth bank, a fake LLM provider, and a tiny resume template."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from docx import Document
from pydantic import BaseModel
from sqlmodel import Session

from app.config import Settings
from app.core.truth_bank import TruthBank, load_truth_bank
from app.db.session import get_engine, init_db
from app.llm.base import LLMProvider
from app.llm.schemas import AnalysisResult, TailorResult

FIXTURES = Path(__file__).parent / "fixtures"
JDS = FIXTURES / "jds"


class FakeProvider(LLMProvider):
    """Returns canned JSON per schema and records every prompt it was sent."""

    name = "fake"
    model = "fake-model"

    def __init__(self, responses: dict[type[BaseModel], Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, str]] = []

    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> str:
        self.calls.append((schema.__name__, system, user))
        value = self.responses[schema]
        return value if isinstance(value, str) else json.dumps(value)


@pytest.fixture
def tb() -> TruthBank:
    return load_truth_bank(FIXTURES / "truth_bank.yaml")


def make_analysis(**overrides: Any) -> dict[str, Any]:
    """A canned call-1 result for a software JD; override any field."""
    base: dict[str, Any] = {
        "jd": {
            "title": "Software Engineer",
            "company": "Example Corp",
            "city": "Riyadh",
            "country": "Saudi Arabia",
            "role_family": "software_ict",
            "must_have_skills": ["React", "REST APIs", "Vue", "Kubernetes"],
            "nice_to_have_skills": ["Gemini API"],
            "min_years_experience": 2,
        },
        "requirements": [
            {
                "requirement": "React",
                "kind": "must",
                "result": "matched",
                "evidence_ids": ["exp_1_b2"],
                "matched_skill": "React",
            },
            {
                "requirement": "REST APIs",
                "kind": "must",
                "result": "matched",
                "evidence_ids": ["exp_1_b2"],
                "matched_skill": "REST APIs",
            },
            {
                "requirement": "Vue",
                "kind": "must",
                "result": "adjacent",
                "evidence_ids": ["exp_1_b2"],
                "matched_skill": "React",
            },
            {"requirement": "Kubernetes", "kind": "must", "result": "missing"},
            {
                "requirement": "Gemini API",
                "kind": "nice",
                "result": "matched",
                "evidence_ids": ["proj_1_b1"],
                "matched_skill": "Gemini API",
            },
        ],
        "relevant_years": 2.5,
        "experience_fit": "strong",
        "experience_note": "about 2.5 years",
        "role_alignment": "strong",
        "role_alignment_note": "same title",
        "hard_conditions": [],
        "logistics": [{"factor": "location", "status": "ok", "note": "Riyadh accepted"}],
        "red_flags": [],
        "summary": ["Good fit.", "Strong React.", "No Kubernetes."],
    }
    for key, value in overrides.items():
        if key == "jd":
            base["jd"] = {**base["jd"], **value}
        else:
            base[key] = value
    return base


def make_tailor(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": "Software Engineer with more than 3 years of experience building React apps.",
        "experience": [
            {
                "source_id": "exp_1",
                "bullets": [
                    {
                        "source_id": "exp_1_b2",
                        "text": "Built React web apps that integrated REST APIs for 12 clients.",
                    },
                    {
                        "source_id": "exp_1_b1",
                        "text": "Developed Flutter applications for Android and iOS from a single codebase.",
                    },
                ],
            },
            {
                "source_id": "exp_2",
                "bullets": [
                    {
                        "source_id": "exp_2_b1",
                        "text": "Delivered technical training to college students.",
                    },
                ],
            },
        ],
        "projects": [
            {
                "source_id": "proj_1",
                "bullets": [
                    {
                        "source_id": "proj_1_b1",
                        "text": "Built an AI research assistant with React and the Gemini API.",
                    },
                ],
            }
        ],
        "skill_groups": [
            {"label": "Frontend", "skills": ["React", "Flutter"]},
            {"label": "Integration", "skills": ["REST APIs", "Gemini API"]},
        ],
        "achievement_ids": ["ach_1", "ach_2"],
        "certification_ids": ["cert_1"],
        "currently_learning": [],
        "cover_letter": " ".join(["I have built React apps that integrated REST APIs."] * 14)
        + "\n\nKind regards,\n{{NAME}}",
        "email_subject": "Application: Software Engineer",
        "email_body": "Please find my resume attached.\n\nKind regards,\n{{NAME}}",
        "whatsapp_message": "Hi, I applied for the Software Engineer role.",
    }
    base.update(overrides)
    return base


@pytest.fixture
def fake_provider() -> Callable[..., FakeProvider]:
    def build(
        analysis: dict[str, Any] | None = None, tailor: dict[str, Any] | None = None
    ) -> FakeProvider:
        return FakeProvider(
            {
                AnalysisResult: analysis or make_analysis(),
                TailorResult: tailor or make_tailor(),
            }
        )

    return build


def write_test_template(path: Path) -> None:
    """A minimal docxtpl template using the same context keys as the real ones."""
    doc = Document()
    for line in [
        "{{ name_upper }}",
        "{{ headline }}",
        "{{ email }} | {{ phone }}",
        "{{ summary }}",
        "{%p for job in experience %}",
        "{{ job.heading }} {{ job.dates }}",
        "{%p for bt in job.bullets %}",
        "- {{ bt }}",
        "{%p endfor %}",
        "{%p endfor %}",
        "{%p for g in skill_groups %}",
        "{{ g.label }}: {{ g.skills_text }}",
        "{%p endfor %}",
        "{%p for c in certifications %}",
        "{{ c.name }} – {{ c.rest }}",
        "{%p endfor %}",
        "{{ languages }}",
    ]:
        doc.add_paragraph(line)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    data = tmp_path / "data"
    for name in ("software_ict.docx", "teaching.docx"):
        write_test_template(data / "templates" / name)
    return Settings(_env_file=None, data_dir=data, libreoffice_path=str(tmp_path / "no-soffice"))


@pytest.fixture
def session(settings: Settings):
    init_db(settings)  # runs the real Alembic migrations against a temp database
    with Session(get_engine(settings)) as s:
        yield s
