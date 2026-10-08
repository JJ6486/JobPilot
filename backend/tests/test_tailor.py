from app.core.tailor import build_resume, format_date
from app.core.truth_bank import TruthBank
from app.llm.schemas import TailorResult
from tests.conftest import make_tailor


def test_format_date() -> None:
    assert format_date("March 2025") == "03/2025"
    assert format_date("Present") == "Present"
    assert format_date("2024") == "2024"


def test_unknown_and_ineligible_ids_are_dropped(tb: TruthBank) -> None:
    tailor = make_tailor(
        experience=[
            {
                "source_id": "exp_1",
                "bullets": [
                    {"source_id": "exp_1_b2", "text": "Built React web apps."},
                    {"source_id": "exp_9_b1", "text": "Led a team of 50."},  # doesn't exist
                    {"source_id": "exp_2_b1", "text": "Wrong entry's bullet."},  # belongs to exp_2
                ],
            },
            {
                "source_id": "exp_3",
                "bullets": [{"source_id": "exp_3_b1", "text": "x"}],
            },  # teaching only
            {"source_id": "exp_99", "bullets": []},
        ],
        skill_groups=[{"label": "All", "skills": ["react.js", "Kubernetes", "Docker"]}],
    )
    content, issues = build_resume(TailorResult.model_validate(tailor), tb, "software_ict")
    kept = [b.source_id for b in content.experience[0].bullets]
    assert kept[0] == "exp_1_b2" and "exp_9_b1" not in kept and "exp_2_b1" not in kept
    assert len(content.experience) == 1
    assert content.skill_groups[0].skills == ["React"]  # alias resolved, unknown dropped
    assert content.currently_learning == ["Docker"]  # 'learning' skill moved out of skills
    assert any("exp_9_b1" in i for i in issues)
    assert any("Kubernetes" in i for i in issues)


def test_facts_come_from_the_truth_bank(tb: TruthBank) -> None:
    content, _ = build_resume(TailorResult.model_validate(make_tailor()), tb, "software_ict")
    job = content.experience[0]
    assert job.heading == "Acme Software"  # "Remote" location is omitted
    assert job.dates == "03/2025 - Present"
    assert content.experience[1].heading == "Beta Labs, Kochi, India"
    assert content.certifications[0].rest == "Example Ministry"
    assert [a.source_id for a in content.achievements] == ["ach_1"]
    assert [b.source_id for b in content.leadership] == ["ach_2"]


def test_teaching_resume_routes_activity_entries(tb: TruthBank) -> None:
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
                "source_id": "exp_1",
                "bullets": [
                    {
                        "source_id": "exp_1_b1",
                        "text": "Developed Flutter applications for Android and iOS from a single codebase.",
                    }
                ],
            },
        ],
        workshop_ids=["ws_1"],
    )
    content, _ = build_resume(TailorResult.model_validate(tailor), tb, "teaching")
    assert content.teaching_roles[0].heading == "Mentor – Club"
    assert content.workshops[0].text == "Intro to Testing – hands-on session on software testing."
    assert [e.source_id for e in content.experience] == ["exp_1"]


def test_falls_back_to_work_history_when_none_selected(tb: TruthBank) -> None:
    content, issues = build_resume(
        TailorResult.model_validate(make_tailor(experience=[])), tb, "software_ict"
    )
    assert [e.source_id for e in content.experience] == ["exp_1", "exp_2"]
    assert any("no work entries" in i for i in issues)


def test_thin_roles_are_topped_up_from_the_original_bullets(tb: TruthBank) -> None:
    tailor = make_tailor(
        experience=[
            {
                "source_id": "exp_1",
                "bullets": [
                    {
                        "source_id": "exp_1_b2",
                        "text": "Built React web apps that integrated REST APIs for 12 clients.",
                    }
                ],
            },
            {"source_id": "exp_2", "bullets": []},
        ]
    )
    content, issues = build_resume(TailorResult.model_validate(tailor), tb, "software_ict")
    # LLM's choice stays first; the rest come back verbatim in truth-bank order
    assert [b.source_id for b in content.experience[0].bullets] == ["exp_1_b2", "exp_1_b1"]
    assert any("added 1 original bullet" in i for i in issues)


def test_headline_follows_the_jd_title(tb: TruthBank) -> None:
    tailored = TailorResult.model_validate(make_tailor(headline="IT Project Coordinator"))
    assert build_resume(tailored, tb, "software_ict")[0].headline == "IT Project Coordinator"
    for unusable in ("", "   ", "x" * 61):
        tailored = TailorResult.model_validate(make_tailor(headline=unusable))
        assert build_resume(tailored, tb, "software_ict")[0].headline == "Software Engineer"
