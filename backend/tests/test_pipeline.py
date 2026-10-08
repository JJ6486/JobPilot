"""End-to-end pipeline runs on the JD fixtures, with a fake LLM (no network)."""

from pathlib import Path

import pytest
from docx import Document
from sqlmodel import Session, select

from app.config import Settings
from app.core.pipeline import run_pipeline
from app.core.truth_bank import TruthBank
from app.db.models import Application, Event, Job, JobRequirement
from tests.conftest import JDS, make_analysis, make_tailor

PRIVATE = ["Test Candidate", "test.candidate@example.com", "500000000", "X1234567", "linkedin"]


def _docx_text(path: str) -> str:
    return "\n".join(p.text for p in Document(path).paragraphs)


def test_software_jd_end_to_end(
    tb: TruthBank, settings: Settings, session: Session, fake_provider
) -> None:
    provider = fake_provider()
    steps: list[tuple[str, str]] = []
    result = run_pipeline(
        (JDS / "software_ict.txt").read_text(encoding="utf-8"),
        tb=tb,
        provider=provider,
        settings=settings,
        session=session,
        source_portal="Indeed",
        on_progress=lambda step, state, _detail: steps.append((step, state)),
    )
    assert result.fit.recommendation == "apply"
    assert result.tailored and result.llm_calls_made == 2
    assert [s for s, state in steps if state == "done"] == [
        "parse",
        "dedupe",
        "score",
        "tailor",
        "letter",
        "save",
    ]

    docx = Path(result.resume_docx)
    assert docx.name.startswith("Test_Candidate_Example_Corp_Software_Engineer_")
    text = _docx_text(result.resume_docx)
    assert "TEST CANDIDATE" in text  # name injected locally at render time
    assert "Acme Software 03/2025 - Present" in text
    assert "Frontend: React, Flutter" in text
    assert result.resume_pdf is None and "LibreOffice not found" in result.pdf_note

    assert result.letters.cover_letter.endswith("Kind regards,\nTest Candidate")
    assert not result.validation.has_high
    app = session.get(Application, result.application_id)
    assert app is not None and app.status == "tailored" and app.fit_score == result.fit.score
    job = session.get(Job, app.job_id)
    assert job is not None and job.company == "Example Corp" and "Himmah" in job.jd_text
    events = session.exec(select(Event).where(Event.application_id == app.id)).all()
    assert [(e.type, e.to_status) for e in events] == [
        ("created", None),
        ("status_change", "tailored"),
    ]
    reqs = session.exec(select(JobRequirement).where(JobRequirement.job_id == job.id)).all()
    assert {(r.skill, r.result) for r in reqs} >= {("Kubernetes", "missing"), ("Vue", "adjacent")}


def test_no_personal_data_is_sent_to_the_llm(
    tb: TruthBank, settings: Settings, session: Session, fake_provider
) -> None:
    provider = fake_provider()
    run_pipeline(
        (JDS / "software_ict.txt").read_text(encoding="utf-8"),
        tb=tb,
        provider=provider,
        settings=settings,
        session=session,
    )
    assert len(provider.calls) == 2
    for _schema, system, user in provider.calls:
        for private in PRIVATE:
            assert private not in system + user, private


def test_teaching_jd_uses_teaching_template(
    tb: TruthBank, settings: Settings, session: Session, fake_provider
) -> None:
    analysis = make_analysis(
        jd={
            "title": "ICT Teacher",
            "company": "Waad Education",
            "city": "Jeddah",
            "role_family": "teaching",
        },
        role_alignment="partial",
    )
    tailor = make_tailor(
        experience=[
            {
                "source_id": "exp_3",
                "bullets": [
                    {
                        "source_id": "exp_3_b1",
                        "text": "Mentored 40 students in project-based learning.",
                    }
                ],
            },
            {
                "source_id": "exp_2",
                "bullets": [
                    {
                        "source_id": "exp_2_b1",
                        "text": "Delivered technical training to college students.",
                    }
                ],
            },
        ],
        workshop_ids=["ws_1"],
    )
    result = run_pipeline(
        (JDS / "teaching.txt").read_text(encoding="utf-8"),
        tb=tb,
        provider=fake_provider(analysis, tailor),
        settings=settings,
        session=session,
    )
    assert result.role_family == "teaching"
    assert result.resume.teaching_roles[0].heading == "Mentor – Club"
    assert "Beta Labs, Kochi, India" in _docx_text(result.resume_docx)


def test_eligibility_blocker_skips_with_a_clear_reason(
    tb: TruthBank, settings: Settings, session: Session, fake_provider
) -> None:
    jd = "Software Engineer, Riyadh. Saudi nationals only. React and REST APIs required."
    analysis = make_analysis(
        hard_conditions=[
            {
                "condition": "Saudi nationals only",
                "category": "nationality",
                "status": "not_met",
                "reason": "The candidate's nationality is Indian.",
            }
        ]
    )
    provider = fake_provider(analysis)
    result = run_pipeline(jd, tb=tb, provider=provider, settings=settings, session=session)
    assert result.fit.recommendation == "skip"
    assert result.fit.score <= 25
    assert "Saudi nationals only" in result.skip_reason
    assert not result.tailored and result.resume_docx is None
    assert len(provider.calls) == 1  # no tailoring call wasted on a blocked job


def test_unmet_qualification_jd_is_scored_not_blocked(
    tb: TruthBank, settings: Settings, session: Session, fake_provider
) -> None:
    analysis = make_analysis(
        jd={
            "title": "Teacher - Math & Physics",
            "company": "Noon Academy",
            "role_family": "teaching",
            "remote_allowed": True,
        },
        hard_conditions=[
            {
                "condition": "Have a recognized teaching qualification",
                "category": "qualification",
                "status": "not_met",
                "reason": "The truth bank lists no teaching qualification.",
            }
        ],
    )
    result = run_pipeline(
        (JDS / "hard_blocker.txt").read_text(encoding="utf-8"),
        tb=tb,
        provider=fake_provider(analysis),
        settings=settings,
        session=session,
    )
    assert result.fit.blockers == []
    assert "Have a recognized teaching qualification" in result.fit.missing
    assert result.tailored and result.resume_docx is not None


@pytest.mark.skip(reason="No Arabic JD fixture yet; Arabic JDs are low priority for now")
def test_arabic_jd() -> None: ...


def test_rerun_uses_cache_and_flags_duplicate(
    tb: TruthBank, settings: Settings, session: Session, fake_provider
) -> None:
    jd = (JDS / "software_ict.txt").read_text(encoding="utf-8")
    run_pipeline(jd, tb=tb, provider=fake_provider(), settings=settings, session=session)
    provider = fake_provider()
    second = run_pipeline(jd, tb=tb, provider=provider, settings=settings, session=session)
    assert provider.calls == [] and second.llm_calls_made == 0
    assert second.duplicates and "same company, title and city" in second.duplicates[0].reasons
