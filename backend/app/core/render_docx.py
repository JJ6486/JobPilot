"""Render `ResumeContent` into the role family's docxtpl template, and optionally to PDF.

This is the only place personal details (name, phone, email, links, certificate URLs) are
combined with the content, locally, after all LLM calls are done.
"""

import re
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate

from app.core.resume import ResumeContent
from app.core.tailor import TEACHING_SKILL_LINE
from app.core.truth_bank import TruthBank


class RenderError(Exception):
    pass


def _display_url(url: str) -> str:
    """'https://www.linkedin.com/in/x/' -> 'linkedin.com/in/x'"""
    return re.sub(r"^https?://(www\.)?", "", url).rstrip("/")


def safe_filename_part(value: str, max_len: int = 40) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_")
    return cleaned[:max_len].rstrip("_") or "Unknown"


def output_filename(full_name: str, company: str, title: str, on: date | None = None) -> str:
    day = (on or date.today()).isoformat()
    parts = [
        safe_filename_part(full_name),
        safe_filename_part(company),
        safe_filename_part(title),
        day,
    ]
    return "_".join(parts) + ".docx"


def build_context(tpl: DocxTemplate, content: ResumeContent, tb: TruthBank) -> dict[str, Any]:
    profile = tb.profile
    link = tpl.build_url_id
    certs_by_id = {c.id: c for c in tb.certifications}
    projects_by_id = tb.project_by_id()

    def chunks(items: list[str], size: int) -> list[str]:
        return [", ".join(items[i : i + size]) for i in range(0, len(items), size)]

    skill_groups = [
        {
            "label": g.label,
            "label_upper": g.label.upper(),
            "skills_text": ", ".join(g.skills),
            "lines": chunks(g.skills, TEACHING_SKILL_LINE),
        }
        for g in content.skill_groups
    ]
    if content.currently_learning:
        learning = ", ".join(content.currently_learning)
        skill_groups.append(
            {
                "label": "Currently learning",
                "label_upper": "CURRENTLY LEARNING",
                "skills_text": learning,
                "lines": [learning],
            }
        )

    def entry(e: Any) -> dict[str, Any]:
        return {
            "heading": e.heading,
            "title": e.title,
            "dates": e.dates,
            "bullets": [b.text for b in e.bullets],
        }

    projects = []
    for p in content.projects:
        url = projects_by_id[p.source_id].url if p.source_id in projects_by_id else ""
        projects.append(
            {
                "name": p.heading,
                "url_id": link(url) if url else "",
                "bullets": [b.text for b in p.bullets],
            }
        )

    certifications = []
    for c in content.certifications:
        url = certs_by_id[c.source_id].url_local_only if c.source_id in certs_by_id else ""
        certifications.append({"name": c.name, "rest": c.rest, "url_id": link(url) if url else ""})

    return {
        "name_upper": profile.full_name.upper(),
        "headline": content.headline,
        "location": profile.location_display or profile.location,
        "phone": profile.phone_display or profile.phone,
        "email": profile.email,
        "email_url_id": link(f"mailto:{profile.email}"),
        "linkedin_text": _display_url(profile.links.linkedin),
        "linkedin_url_id": link(profile.links.linkedin),
        "portfolio_text": _display_url(profile.links.portfolio),
        "portfolio_url_id": link(profile.links.portfolio),
        "summary": content.summary,
        "education": [
            {
                "institution": e.institution,
                "dates": f"{e.start} - {e.end}",
                "degree": f"{e.degree} in {e.field}" if e.field else e.degree,
            }
            for e in tb.education
        ],
        "experience": [entry(e) for e in content.experience],
        "teaching_intro": [b.text for b in content.teaching_intro],
        "workshops": [b.text for b in content.workshops],
        "teaching_roles": [entry(e) for e in content.teaching_roles],
        "projects": projects,
        "skill_groups": skill_groups,
        "achievements": [a.model_dump() for a in content.achievements],
        "certifications": certifications,
        "leadership": [b.text for b in content.leadership],
        "languages": "  |  ".join(
            f"{lang.name} ({lang.level})" for lang in tb.constraints.languages
        ),
        "nationality": tb.constraints.nationality,
        "visa_status": tb.constraints.visa_status,
    }


def render_docx(content: ResumeContent, tb: TruthBank, template: Path, dest: Path) -> Path:
    if not template.is_file():
        raise RenderError(f"Template not found: {template}")
    tpl = DocxTemplate(str(template))
    tpl.render(build_context(tpl, content, tb), autoescape=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tpl.save(str(dest))
    return dest


def convert_to_pdf(docx: Path, soffice: Path, timeout_s: float = 120.0) -> Path:
    """Convert with headless LibreOffice, using a throwaway profile so a running
    LibreOffice window doesn't block the conversion."""
    with tempfile.TemporaryDirectory(prefix="jobpilot-lo-") as profile_dir:
        cmd = [
            str(soffice),
            f"-env:UserInstallation={Path(profile_dir).as_uri()}",
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(docx.parent),
            str(docx),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            raise RenderError("LibreOffice timed out converting to PDF") from exc
        except subprocess.CalledProcessError as exc:
            raise RenderError(
                f"LibreOffice failed: {exc.stderr.decode(errors='replace')[:300]}"
            ) from exc
    pdf = docx.with_suffix(".pdf")
    if not pdf.is_file():
        raise RenderError("LibreOffice finished but no PDF was produced")
    return pdf
