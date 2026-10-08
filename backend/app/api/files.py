"""GET /api/base-resumes: which original resume and template each role family uses."""

from docx import Document
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import SettingsDep, TruthBankDep

router = APIRouter(tags=["files"])


class BaseResume(BaseModel):
    role_family: str
    headline: str
    base_resume: str
    base_resume_found: bool
    template: str
    template_found: bool


@router.get("/base-resumes", response_model=list[BaseResume])
def base_resumes(settings: SettingsDep, tb: TruthBankDep) -> list[BaseResume]:
    templates = settings.data_dir / "templates"
    return [
        BaseResume(
            role_family=family,
            headline=cfg.headline,
            base_resume=cfg.base_resume,
            base_resume_found=(settings.base_resumes_dir / cfg.base_resume).is_file(),
            template=cfg.template,
            template_found=(templates / cfg.template).is_file(),
        )
        for family, cfg in tb.role_families.items()
    ]


class BaseResumeText(BaseModel):
    role_family: str
    file: str
    lines: list[str]


@router.get("/base-resumes/{role_family}/text", response_model=BaseResumeText)
def base_resume_text(role_family: str, settings: SettingsDep, tb: TruthBankDep) -> BaseResumeText:
    """Plain text of the original resume, for the Review screen's diff view."""
    cfg = tb.role_families.get(role_family)  # type: ignore[call-overload]
    if cfg is None:
        raise HTTPException(404, f"Unknown role family {role_family!r}")
    path = settings.base_resumes_dir / cfg.base_resume
    if not path.is_file():
        raise HTTPException(404, f"Base resume not found: {path.name}")
    lines = [p.text.strip() for p in Document(str(path)).paragraphs if p.text.strip()]
    return BaseResumeText(role_family=role_family, file=path.name, lines=lines)
