from app.core.resume import ResumeContent
from app.core.tailor import build_resume
from app.core.truth_bank import TruthBank
from app.core.validator import Validator
from app.llm.schemas import TailorResult
from tests.conftest import make_tailor


def _resume(tb: TruthBank, **overrides) -> ResumeContent:
    content, _ = build_resume(
        TailorResult.model_validate(make_tailor(**overrides)), tb, "software_ict"
    )
    return content


def _highs(report) -> list[str]:
    return [w.text for w in report.warnings if w.severity == "high"]


def test_truthful_resume_has_no_warnings(tb: TruthBank) -> None:
    report = Validator(tb).validate(_resume(tb), {})
    assert report.warnings == []


def test_skill_not_in_truth_bank_is_high_severity(tb: TruthBank) -> None:
    content = _resume(tb, summary="Engineer experienced with React and Kubernetes.")
    report = Validator(tb).validate(content, {})
    assert "Kubernetes" in _highs(report)
    assert report.has_high


def test_adjacent_skill_on_resume_is_high(tb: TruthBank) -> None:
    content = _resume(tb, summary="Builds apps with React and Vue.")
    assert "Vue" in _highs(Validator(tb).validate(content, {}))


def test_invented_number_and_bullet_drift_are_high(tb: TruthBank) -> None:
    content = _resume(tb)
    content.experience[0].bullets[0].text = "Built React and GraphQL apps for 30 clients."
    highs = _highs(Validator(tb).validate(content, {}))
    assert "30" in highs
    assert "GraphQL" in highs


def test_learning_phrasing_in_letter_is_medium_but_claim_is_high(tb: TruthBank) -> None:
    v = Validator(tb)
    honest = v.validate(_resume(tb), {"whatsapp_message": "I use React and am keen to learn Vue."})
    assert [w.severity for w in honest.warnings if w.text == "Vue"] == ["medium"]
    claim = v.validate(_resume(tb), {"whatsapp_message": "I have shipped Vue apps."})
    assert "Vue" in _highs(claim)


def test_credentials_and_never_claim_are_high(tb: TruthBank) -> None:
    letter = {"cover_letter": "I hold a PGCE. I also have a Saudi teaching licence."}
    highs = _highs(Validator(tb).validate(_resume(tb), letter))
    assert "PGCE" in highs
    assert any("teaching licence" in h.lower() for h in highs)


def test_letter_length_and_avoided_phrases_are_medium(tb: TruthBank) -> None:
    report = Validator(tb).validate(_resume(tb), {"cover_letter": "I am passionate about React."})
    mediums = {w.message for w in report.warnings if w.severity == "medium"}
    assert any("100-200 words" in m for m in mediums)
    assert any("passionate" in m for m in mediums)


def test_jd_company_name_is_allowed_in_letters(tb: TruthBank) -> None:
    letter = {"whatsapp_message": "I applied to MOZN for the React role."}
    assert Validator(tb).validate(_resume(tb), letter).warnings != []
    assert Validator(tb, allowed_extra=["MOZN"]).validate(_resume(tb), letter).warnings == []


def test_other_learning_phrasings_are_medium(tb: TruthBank) -> None:
    letter = {
        "cover_letter": "I am confident in quickly mastering containerization tools like Vue."
    }
    assert [
        w.severity for w in Validator(tb).validate(_resume(tb), letter).warnings if w.text == "Vue"
    ] == ["medium"]


def test_rewording_may_name_tools_recorded_for_that_job(tb: TruthBank) -> None:
    content = _resume(tb)
    # exp_1_b1's job (Acme) records React in exp_1_b2's skills, so naming it is a true statement.
    content.experience[0].bullets[
        1
    ].text = "Developed Flutter applications for Android and iOS from a single codebase, alongside React."
    assert Validator(tb).validate(content, {}).warnings == []


def test_rewording_with_a_tool_from_another_job_is_flagged_once(tb: TruthBank) -> None:
    content = _resume(tb)
    beta = content.experience[1].bullets[0]  # Beta Labs: training only, no React
    beta.text = "Delivered technical training to college students using React.js and React."
    highs = [w for w in Validator(tb).validate(content, {}).warnings if w.severity == "high"]
    assert [w.text for w in highs] == ["React"]  # alias and name collapse to one warning
    assert "doesn't link it to this job" in highs[0].message
