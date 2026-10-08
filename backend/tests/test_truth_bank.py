import json
from pathlib import Path

import pytest
import yaml

from app.core.truth_bank import TruthBank, TruthBankError, parse_truth_bank
from tests.conftest import FIXTURES


def _raw() -> dict:
    return yaml.safe_load((FIXTURES / "truth_bank.yaml").read_text(encoding="utf-8"))


def test_fixture_loads(tb: TruthBank) -> None:
    assert tb.profile.full_name == "Test Candidate"
    assert tb.find_skill("react.js").name == "React"  # alias, case-insensitive


def test_llm_view_strips_personal_data(tb: TruthBank) -> None:
    view = json.dumps(tb.llm_view())
    for private in [
        "Test Candidate",
        "test.candidate@example.com",
        "500000000",
        "linkedin",
        "X1234567",
        "verify.example.com",
        "example.com/chat",
        "min_salary",
    ]:
        assert private not in view, private
    assert "Acme Software" in view  # experience content does go through


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda d: d["skills"][0].update(level="expert"), "skills.0.level"),
        (lambda d: d["skills"][0].update(evidance=["x"]), "skills.0.evidance"),
        (lambda d: d["skills"][0].update(evidence=["nope_1"]), "unknown id 'nope_1'"),
        (
            lambda d: d["experience"][0]["bullets"][0].update(id="exp_1_b2"),
            "duplicate id 'exp_1_b2'",
        ),
        (
            lambda d: d["experience"][0]["bullets"][0].update(skills=["Cobol"]),
            "'Cobol' is not in the skills list",
        ),
        (lambda d: d["projects"][0].update(name="<<FILL>>"), "projects[0].name: still contains"),
    ],
)
def test_errors_point_at_the_field(mutate, expected: str) -> None:
    data = _raw()
    mutate(data)
    with pytest.raises(TruthBankError) as exc:
        parse_truth_bank(data)
    assert any(expected in p for p in exc.value.problems), exc.value.problems


def test_missing_file_is_reported(tmp_path: Path) -> None:
    from app.core.truth_bank import load_truth_bank

    with pytest.raises(TruthBankError, match="file not found"):
        load_truth_bank(tmp_path / "nope.yaml")
