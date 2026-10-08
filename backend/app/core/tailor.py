"""LLM call 2: choose and order truth-bank content for one JD, and write the messages.

The LLM returns ids plus lightly reworded bullet text (`TailorResult`). `build_resume()` then
enforces the rules in code: unknown or ineligible ids are dropped, "learning" skills are moved
to "Currently learning", and everything else (dates, company names, certifications) is filled
in from the truth bank itself, never from LLM text.
"""

import json
import re

from rapidfuzz import fuzz

from app.core.resume import (
    ResumeAchievement,
    ResumeBullet,
    ResumeCertification,
    ResumeContent,
    ResumeEntry,
    ResumeSkillGroup,
)
from app.core.truth_bank import Experience, RoleFamily, TruthBank
from app.llm.base import LLMProvider, StatusCallback, generate_structured
from app.llm.cache import LLMCache, text_hash
from app.llm.prompts import load_prompt, load_sections
from app.llm.schemas import AnalysisResult, TailoredEntry, TailorResult

_MONTH_NAMES = (
    "january february march april may june july august september october november december"
)
_MONTHS = {m: i for i, m in enumerate(_MONTH_NAMES.split(), start=1)}
TEACHING_SKILL_LINE = 4  # skills per bullet line on the teaching resume
# Minimum bullets per work entry (current role, previous role, older roles). If the LLM keeps
# fewer, the rest are filled from the truth bank in its original order, skipping near-duplicates.
MIN_WORK_BULLETS: dict[RoleFamily, tuple[int, int, int]] = {
    "software_ict": (7, 4, 2),
    "teaching": (4, 3, 2),
}
NEAR_DUPLICATE = 80
MAX_HEADLINE_CHARS = 60


def format_date(value: str) -> str:
    """'March 2025' -> '03/2025'; '2024' and 'Present' are kept as-is."""
    match = re.fullmatch(r"\s*([A-Za-z]+)\s+(\d{4})\s*", value)
    if match and match.group(1).lower() in _MONTHS:
        return f"{_MONTHS[match.group(1).lower()]:02d}/{match.group(2)}"
    return value.strip()


def run_tailor(
    provider: LLMProvider,
    analysis: AnalysisResult,
    tb: TruthBank,
    role_family: RoleFamily,
    cache: LLMCache,
    jd_text: str,
    on_status: StatusCallback | None = None,
) -> tuple[TailorResult, bool]:
    """Return (tailor result, from_cache)."""
    prompt = load_prompt("tailor")
    rules_version, rules = load_sections("tailor_rules")
    key = cache.key(
        "tailor",
        text_hash(jd_text),
        tb.content_hash(),
        text_hash(analysis.model_dump_json()),
        prompt.cache_id,
        rules_version,
        provider.model,
        role_family,
    )
    if (cached := cache.get(key, TailorResult)) is not None:
        return cached, True

    prefs = tb.writing_preferences
    system, user = prompt.render(
        TRUTH_BANK=json.dumps(tb.llm_view(), ensure_ascii=False),
        ANALYSIS=analysis.model_dump_json(),
        ROLE_FAMILY=role_family,
        RESUME_RULES=rules[role_family],
        TONE=prefs.tone,
        AVOID_PHRASES=", ".join(prefs.avoid_phrases) or "(none)",
    )
    result = generate_structured(provider, system, user, TailorResult, on_status)
    cache.put(key, result)
    return result, False


def _entry_heading(exp: Experience) -> str:
    if exp.kind == "activity":
        return f"{exp.title} – {exp.short_name or exp.company}"
    if exp.location and exp.location.lower() != "remote":
        return f"{exp.company}, {exp.location}"
    return exp.company


def _bullets(
    entry: TailoredEntry, allowed: dict[str, str], issues: list[str], where: str
) -> list[ResumeBullet]:
    out: list[ResumeBullet] = []
    seen: set[str] = set()
    for b in entry.bullets:
        if b.source_id not in allowed:
            issues.append(f"{where}: dropped bullet with unknown source_id {b.source_id!r}")
            continue
        if b.source_id in seen:
            continue
        seen.add(b.source_id)
        out.append(ResumeBullet(source_id=b.source_id, text=b.text.strip() or allowed[b.source_id]))
    return out


def build_resume(
    tailor: TailorResult, tb: TruthBank, role_family: RoleFamily
) -> tuple[ResumeContent, list[str]]:
    """Turn the LLM's id-based selection into resume content, enforcing the truth bank."""
    issues: list[str] = []
    family = tb.role_families[role_family]
    experiences = tb.experience_by_id()
    projects = tb.project_by_id()

    work: list[ResumeEntry] = []
    teaching_roles: list[ResumeEntry] = []
    teaching_intro: list[ResumeBullet] = []
    for entry in tailor.experience:
        exp = experiences.get(entry.source_id)
        if exp is None or role_family not in exp.role_families:
            issues.append(
                f"experience: dropped {entry.source_id!r} (unknown or not for {role_family})"
            )
            continue
        if exp.kind == "activity" and role_family != "teaching":
            issues.append(f"experience: dropped activity {exp.id!r} (not shown on this resume)")
            continue
        bullets = _bullets(entry, {b.id: b.text for b in exp.bullets}, issues, exp.id)
        if not bullets:
            continue
        if exp.kind == "activity" and not exp.short_name:
            teaching_intro.extend(bullets)  # general teaching bullets with no sub-heading
            continue
        resume_entry = ResumeEntry(
            source_id=exp.id,
            heading=_entry_heading(exp),
            title=exp.title if exp.kind == "work" else "",
            dates=f"{format_date(exp.start)} - {format_date(exp.end)}"
            if exp.kind == "work"
            else "",
            bullets=bullets,
        )
        (work if exp.kind == "work" else teaching_roles).append(resume_entry)

    _top_up(work, experiences, role_family, issues)

    if not work:  # never render a resume without its work history
        issues.append("experience: LLM selected no work entries; using all eligible ones")
        for exp in tb.experience:
            if exp.kind == "work" and role_family in exp.role_families:
                work.append(
                    ResumeEntry(
                        source_id=exp.id,
                        heading=_entry_heading(exp),
                        title=exp.title,
                        dates=f"{format_date(exp.start)} - {format_date(exp.end)}",
                        bullets=[
                            ResumeBullet(source_id=b.id, text=b.text) for b in exp.bullets[:4]
                        ],
                    )
                )

    project_entries: list[ResumeEntry] = []
    for entry in tailor.projects:
        proj = projects.get(entry.source_id)
        if proj is None or role_family not in proj.role_families:
            issues.append(
                f"projects: dropped {entry.source_id!r} (unknown or not for {role_family})"
            )
            continue
        bullets = _bullets(entry, {b.id: b.text for b in proj.bullets}, issues, proj.id)
        if bullets:
            project_entries.append(
                ResumeEntry(source_id=proj.id, heading=proj.name, bullets=bullets)
            )

    skill_groups, learning = _skill_groups(tailor, tb, issues)

    workshops_by_id = {w.id: w for w in tb.workshops}
    workshops = (
        [
            ResumeBullet(source_id=w.id, text=f"{w.title} – {w.text}")
            for wid in tailor.workshop_ids
            if (w := workshops_by_id.get(wid)) is not None
        ]
        if role_family == "teaching"
        else []
    )

    achievements_by_id = {a.id: a for a in tb.achievements}
    achievements: list[ResumeAchievement] = []
    leadership: list[ResumeBullet] = []
    for aid in tailor.achievement_ids:
        a = achievements_by_id.get(aid)
        if a is None:
            issues.append(f"achievements: dropped unknown id {aid!r}")
        elif a.section == "leadership":
            leadership.append(ResumeBullet(source_id=a.id, text=a.text))
        elif role_family == "software_ict":
            meta = a.year if not a.issuer or a.issuer in a.title else f"{a.issuer}, {a.year}"
            achievements.append(
                ResumeAchievement(source_id=a.id, title=a.title, meta=meta, text=a.text)
            )

    certs_by_id = {c.id: c for c in tb.certifications}
    certifications = [
        ResumeCertification(
            source_id=c.id,
            name=c.name,
            rest=c.issuer + (f" ({c.year}): {c.detail}" if c.detail else ""),
        )
        for cid in tailor.certification_ids
        if (c := certs_by_id.get(cid)) is not None
    ]

    content = ResumeContent(
        role_family=role_family,
        headline=_headline(tailor.headline, family.headline),
        summary=tailor.summary.strip() or family.summary_options[0].text,
        experience=work,
        teaching_intro=teaching_intro,
        teaching_roles=teaching_roles,
        workshops=workshops,
        projects=project_entries,
        skill_groups=skill_groups,
        currently_learning=learning,
        achievements=achievements,
        certifications=certifications,
        leadership=leadership,
    )
    return content, issues


def _top_up(
    work: list[ResumeEntry],
    experiences: dict[str, Experience],
    role_family: RoleFamily,
    issues: list[str],
) -> None:
    """Keep each role's breadth: add back original bullets if the LLM trimmed too far."""
    current, previous, older = MIN_WORK_BULLETS[role_family]
    for index, entry in enumerate(work):
        minimum = current if index == 0 else previous if index == 1 else older
        added = 0
        for bullet in experiences[entry.source_id].bullets:
            if len(entry.bullets) >= minimum:
                break
            chosen = [b.text for b in entry.bullets]
            if bullet.id in {b.source_id for b in entry.bullets} or any(
                fuzz.token_set_ratio(bullet.text, text) >= NEAR_DUPLICATE for text in chosen
            ):
                continue
            entry.bullets.append(ResumeBullet(source_id=bullet.id, text=bullet.text))
            added += 1
        if added:
            issues.append(f"experience: added {added} original bullet(s) back to {entry.source_id}")


def _headline(suggested: str, default: str) -> str:
    """The JD's (cleaned) job title as the resume headline; the role family's default if the
    LLM gave nothing usable."""
    title = " ".join(suggested.split())
    return title if 0 < len(title) <= MAX_HEADLINE_CHARS else default


def _skill_groups(
    tailor: TailorResult, tb: TruthBank, issues: list[str]
) -> tuple[list[ResumeSkillGroup], list[str]]:
    groups: list[ResumeSkillGroup] = []
    learning: list[str] = []
    used: set[str] = set()
    for group in tailor.skill_groups:
        names: list[str] = []
        for raw in group.skills:
            skill = tb.find_skill(raw)
            if skill is None:
                issues.append(f"skills: dropped {raw!r} (not in truth bank)")
            elif skill.level == "learning":
                learning.append(skill.name)
            elif skill.name not in used:
                used.add(skill.name)
                names.append(skill.name)
        if names:
            groups.append(ResumeSkillGroup(label=group.label.strip(), skills=names))
    for raw in tailor.currently_learning:
        skill = tb.find_skill(raw)
        if skill is not None and skill.level == "learning" and skill.name not in learning:
            learning.append(skill.name)
        elif skill is None or skill.level != "learning":
            issues.append(f"currently learning: dropped {raw!r} (not a 'learning' skill)")
    return groups, learning
