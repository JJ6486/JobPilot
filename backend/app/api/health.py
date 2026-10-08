"""GET /api/health: reports whether each dependency the pipeline needs is ready."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.core.libreoffice import find_soffice
from app.core.truth_bank import TruthBankError, load_truth_bank

router = APIRouter()


class LLMStatus(BaseModel):
    configured: bool
    provider: str
    model: str
    detail: str


class LibreOfficeStatus(BaseModel):
    found: bool
    path: str | None
    detail: str


class TruthBankStatus(BaseModel):
    found: bool
    valid: bool
    detail: str
    problems: list[str] = []


class TemplatesStatus(BaseModel):
    files: list[str]
    missing: list[str]
    detail: str


class HealthResponse(BaseModel):
    status: str
    llm: LLMStatus
    libreoffice: LibreOfficeStatus
    truth_bank: TruthBankStatus
    templates: TemplatesStatus


def _llm_status(settings: Settings) -> LLMStatus:
    if settings.llm_provider == "gemini":
        configured = bool(settings.gemini_api_key)
        missing = "GEMINI_API_KEY"
    else:
        configured = bool(settings.openai_compat_base_url and settings.llm_model)
        missing = "OPENAI_COMPAT_BASE_URL and LLM_MODEL"
    detail = "Ready." if configured else f"Set {missing} in .env."
    return LLMStatus(
        configured=configured,
        provider=settings.llm_provider,
        model=settings.llm_model or "(provider default)",
        detail=detail,
    )


def _libreoffice_status(settings: Settings) -> LibreOfficeStatus:
    path = find_soffice(settings.libreoffice_path)
    if path:
        return LibreOfficeStatus(found=True, path=str(path), detail="PDF export available.")
    return LibreOfficeStatus(
        found=False,
        path=None,
        detail="LibreOffice not found. Resumes will be DOCX only (PDF export disabled).",
    )


def _truth_bank_status(path: Path) -> TruthBankStatus:
    if not path.is_file():
        return TruthBankStatus(found=False, valid=False, detail=f"Not found at {path}.")
    try:
        tb = load_truth_bank(path)
    except TruthBankError as exc:
        n = len(exc.problems)
        return TruthBankStatus(
            found=True, valid=False, detail=f"{n} problem(s) to fix.", problems=exc.problems
        )
    return TruthBankStatus(
        found=True,
        valid=True,
        detail=f"{len(tb.experience)} roles, {len(tb.projects)} projects, {len(tb.skills)} skills.",
    )


def _templates_status(settings: Settings) -> TemplatesStatus:
    directory = settings.data_dir / "templates"
    expected = ["software_ict.docx", "teaching.docx"]
    files = sorted(p.name for p in directory.glob("*.docx")) if directory.is_dir() else []
    missing = [name for name in expected if name not in files]
    detail = f"Missing in {directory}: {', '.join(missing)}" if missing else "Both templates found."
    return TemplatesStatus(files=files, missing=missing, detail=detail)


@router.get("/health", response_model=HealthResponse)
def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(
        status="ok",
        llm=_llm_status(settings),
        libreoffice=_libreoffice_status(settings),
        truth_bank=_truth_bank_status(settings.truth_bank_path),
        templates=_templates_status(settings),
    )
