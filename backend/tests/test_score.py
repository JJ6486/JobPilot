from app.core.score import compute_score
from app.core.truth_bank import TruthBank
from app.llm.schemas import AnalysisResult
from tests.conftest import make_analysis


def _score(tb: TruthBank, jd_text: str = "", **overrides):
    return compute_score(AnalysisResult.model_validate(make_analysis(**overrides)), tb, jd_text)


def test_score_is_computed_deterministically_from_judgements(tb: TruthBank) -> None:
    fit = _score(tb)
    # must: (1 + 1 + 0.5 + 0) / 4 * 40 = 25; experience 20; role 15; nice 10; logistics 15
    assert fit.breakdown.model_dump() == {
        "must": 25.0,
        "experience": 20.0,
        "role": 15.0,
        "nice": 10.0,
        "logistics": 15.0,
    }
    assert fit.score == 85
    assert fit.recommendation == "apply"
    assert fit.matched == ["React", "REST APIs", "Gemini API"]
    assert fit.adjacent == ["Vue"]
    assert fit.missing == ["Kubernetes"]
    assert _score(tb) == fit  # same judgements, same result


def test_years_shortfall_reduces_experience_points(tb: TruthBank) -> None:
    fit = _score(tb, jd={"min_years_experience": 5}, relevant_years=2.5)
    assert fit.breakdown.experience == 10.0  # 2.5 / 5 of 20


def test_verified_hard_blocker_caps_score_and_forces_skip(tb: TruthBank) -> None:
    jd = "Senior role. Saudi nationals only. React required."
    fit = _score(
        tb,
        jd_text=jd,
        hard_conditions=[
            {
                "condition": "Saudi nationals only",
                "category": "nationality",
                "status": "not_met",
                "reason": "Candidate is Indian",
            }
        ],
    )
    assert fit.recommendation == "skip"
    assert fit.score <= 25
    assert fit.blockers == ["Saudi nationals only: Candidate is Indian"]


def test_blocker_not_in_jd_text_is_ignored(tb: TruthBank) -> None:
    fit = _score(
        tb,
        jd_text="We build React apps in Riyadh.",
        hard_conditions=[
            {
                "condition": "Must hold a valid teaching licence",
                "status": "not_met",
                "reason": "none",
            }
        ],
    )
    assert fit.blockers == []
    assert any("not found in the JD" in f for f in fit.red_flags)


def test_years_condition_is_not_a_blocker(tb: TruthBank) -> None:
    fit = _score(
        tb,
        jd_text="3+ years of teaching experience",
        hard_conditions=[
            {
                "condition": "3+ years of teaching experience",
                "status": "not_met",
                "reason": "0 years",
            }
        ],
    )
    assert fit.blockers == []


def test_location_outside_accepted_cities_blocks(tb: TruthBank) -> None:
    fit = _score(tb, jd={"city": "Tabuk", "remote_allowed": False})
    assert fit.recommendation == "skip"
    assert "Tabuk" in fit.blockers[0]


def test_match_without_valid_evidence_is_downgraded(tb: TruthBank) -> None:
    fit = _score(
        tb,
        requirements=[
            {
                "requirement": "Kubernetes",
                "kind": "must",
                "result": "matched",
                "evidence_ids": ["made_up_id"],
                "matched_skill": "Kubernetes",
            },
            {
                "requirement": "Docker",
                "kind": "must",
                "result": "matched",
                "evidence_ids": [],
                "matched_skill": "Docker",
            },  # only 'learning'
            {
                "requirement": "English",
                "kind": "must",
                "result": "matched",
                "evidence_ids": ["constraints.languages"],
            },
        ],
    )
    assert fit.missing == ["Kubernetes", "Docker"]
    assert fit.matched == ["English"]


def test_unmet_qualification_lowers_score_but_does_not_block(tb: TruthBank) -> None:
    jd = "Requirements: Proven teaching qualifications (Bachelor / Masters). React."
    condition = {
        "condition": "Proven teaching qualifications",
        "category": "qualification",
        "status": "not_met",
        "reason": "No teaching qualification in the truth bank",
    }
    fit = _score(tb, jd_text=jd, hard_conditions=[condition])
    assert fit.blockers == []
    assert fit.recommendation != "skip" or fit.score < 45  # decided by score, not a cap
    assert "Proven teaching qualifications" in fit.missing
    # counted once, as an extra missing must-have: (1 + 1 + 0.5 + 0 + 0) / 5 * 40 = 20
    assert fit.breakdown.must == 20.0
    assert any("not a blocker" in f for f in fit.red_flags)


def test_unmet_qualification_already_listed_is_not_double_counted(tb: TruthBank) -> None:
    jd = "Must have Kubernetes certification."
    condition = {
        "condition": "Kubernetes",
        "category": "qualification",
        "status": "not_met",
        "reason": "none",
    }
    fit = _score(tb, jd_text=jd, hard_conditions=[condition])
    assert fit.missing.count("Kubernetes") == 1
    assert fit.breakdown.must == 25.0
