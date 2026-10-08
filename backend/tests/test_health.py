import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from tests.conftest import FIXTURES, write_test_template


@pytest.fixture
def client(tmp_path: Path):
    def override() -> Settings:
        return Settings(_env_file=None, data_dir=tmp_path, gemini_api_key="")

    app.dependency_overrides[get_settings] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_reports_missing_pieces(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["llm"]["configured"] is False
    assert body["truth_bank"]["found"] is False
    assert body["templates"]["missing"] == ["software_ict.docx", "teaching.docx"]


def test_health_validates_truth_bank_and_finds_templates(
    client: TestClient, tmp_path: Path
) -> None:
    shutil.copy(FIXTURES / "truth_bank.yaml", tmp_path / "truth_bank.yaml")
    for name in ("software_ict.docx", "teaching.docx"):
        write_test_template(tmp_path / "templates" / name)

    body = client.get("/api/health").json()
    assert body["truth_bank"]["valid"] is True
    assert body["truth_bank"]["problems"] == []
    assert body["templates"]["missing"] == []


def test_health_lists_truth_bank_problems(client: TestClient, tmp_path: Path) -> None:
    (tmp_path / "truth_bank.yaml").write_text("profile:\n  full_name: Test\n", "utf-8")
    body = client.get("/api/health").json()
    assert body["truth_bank"]["valid"] is False
    assert any("constraints" in p for p in body["truth_bank"]["problems"])
