"""Turn the LLM's per-requirement judgements into a fit score, deterministically.

Weights: must-haves 40, experience 20, role alignment 15, nice-to-haves 10, logistics 15.
Before scoring, every judgement is checked against the truth bank: a "matched" or "adjacent"
claim whose evidence ids don't exist is downgraded, so the LLM can't talk the score up.
"""

import re
from typing import Literal

from pydantic import BaseModel
from rapidfuzz import fuzz

from app.core.truth_bank import TruthBank
from app.llm.schemas import AnalysisResult, RequirementJudgement

WEIGHTS = {"must": 40.0, "experience": 20.0, "role": 15.0, "nice": 10.0, "logistics": 15.0}
FIT_FRACTION = {"strong": 1.0, "partial": 0.5, "weak": 0.0}
RESULT_FRACTION = {"matched": 1.0, "adjacent": 0.5, "missing": 0.0}
EMPTY_LIST_FRACTION = 0.5  # JD lists no skills of this kind: neither reward nor punish
BLOCKER_CAP = 25.0
APPLY_AT = 70.0
MAYBE_AT = 45.0
LOGISTICS_CONCERN_PENALTY = 5.0
_LICENCE = re.compile(r"licen[cs]e|\u0631\u062e\u0635\u0629", re.I)  # licence / "رخصة"
BLOCKING_CATEGORIES = {"nationality", "visa", "gender", "location"}
CONDITION_IN_JD = 70  # min fuzzy match between a blocker's wording and the JD text
_YEARS = re.compile(r"\b\d+\s*\+?\s*(years?|yrs?)\b", re.I)
# Constraint fields judgements may cite as evidence (languages, visa, ...); they have no ids.
CONSTRAINT_EVIDENCE = {
    "constraints.languages",
    "constraints.visa_status",
    "constraints.nationality",
    "constraints.accepted_cities",
    "constraints.open_to_relocation",
    "constraints.open_to_remote",
}

Recommendation = Literal["apply", "maybe", "skip"]


class ScoreBreakdown(BaseModel):
    must: float
    experience: float
    role: float
    nice: float
    logistics: float


class FitScore(BaseModel):
    score: int
    recommendation: Recommendation
    breakdown: ScoreBreakdown
    blockers: list[str]
    matched: list[str]
    adjacent: list[str]
    missing: list[str]
    red_flags: list[str]
    summary: list[str]
    requirements: list[RequirementJudgement]  # after evidence checks


def verify_judgements(
    analysis: AnalysisResult, tb: TruthBank
) -> tuple[list[RequirementJudgement], list[str]]:
    """Downgrade judgements whose evidence doesn't exist in the truth bank."""
    known_ids = tb.all_ids() | CONSTRAINT_EVIDENCE
    checked: list[RequirementJudgement] = []
    flags: list[str] = []
    for req in analysis.requirements:
        req = req.model_copy(deep=True)
        valid_ids = [i for i in req.evidence_ids if i in known_ids]
        skill = tb.find_skill(req.matched_skill) if req.matched_skill else None
        if req.result == "matched":
            if skill and skill.level == "learning":
                req.result, req.note = "missing", f"only 'learning' level: {skill.name}"
                flags.append(f"{req.requirement!r}: downgraded (skill is only being learned)")
            elif not valid_ids and skill is None:
                req.result = "missing"
                flags.append(f"{req.requirement!r}: downgraded to missing (no valid evidence)")
        elif req.result == "adjacent" and not valid_ids and skill is None:
            req.result = "missing"
            flags.append(f"{req.requirement!r}: adjacent claim had no valid evidence")
        req.evidence_ids = valid_ids
        checked.append(req)
    return checked, flags


def _fraction(reqs: list[RequirementJudgement]) -> float:
    if not reqs:
        return EMPTY_LIST_FRACTION
    return sum(RESULT_FRACTION[r.result] for r in reqs) / len(reqs)


def _experience_fraction(analysis: AnalysisResult) -> float:
    level = FIT_FRACTION[analysis.experience_fit]
    min_years = analysis.jd.min_years_experience
    if min_years and min_years > 0:
        by_years = min(1.0, max(0.0, analysis.relevant_years) / min_years)
        return min(level, by_years)
    return level


def _location_blocker(analysis: AnalysisResult, tb: TruthBank) -> str | None:
    """Code-level check that doesn't rely on the LLM noticing."""
    jd, c = analysis.jd, tb.constraints
    if not jd.city or jd.remote_allowed or c.open_to_relocation:
        return None
    accepted = {city.lower() for city in c.accepted_cities}
    if jd.city.lower() not in accepted:
        return f"Job is in {jd.city}, which isn't in your accepted cities"
    return None


def _check_conditions(
    analysis: AnalysisResult, jd_text: str
) -> tuple[list[str], list[str], list[str]]:
    """Sort "not_met" conditions into (blockers, flags, gaps).

    Only eligibility conditions (nationality, visa, gender, location) block, and only if their
    wording can be found in the JD (so the LLM can't invent one). Unmet qualifications,
    licences and degrees are gaps: scored as missing must-haves, never blockers. Years of
    experience are scored under experience.
    """
    blockers: list[str] = []
    flags: list[str] = []
    gaps: list[str] = []
    haystack = jd_text.lower()
    for h in analysis.hard_conditions:
        if h.status == "unclear":
            flags.append(f"Unclear condition: {h.condition} ({h.reason})")
        if h.status != "not_met":
            continue
        if _YEARS.search(h.condition):
            flags.append(f"{h.condition} (scored under experience, not a blocker)")
        elif jd_text and fuzz.partial_ratio(h.condition.lower(), haystack) < CONDITION_IN_JD:
            flags.append(f"Possible condition not found in the JD text, ignored: {h.condition}")
        elif h.category in BLOCKING_CATEGORIES:
            blockers.append(f"{h.condition}: {h.reason}")
        else:
            gaps.append(h.condition)
            flags.append(f"Not met (lowers the score, not a blocker): {h.condition}")
    return blockers, flags, gaps


def _add_gaps(requirements: list[RequirementJudgement], gaps: list[str]) -> None:
    """Make sure each unmet qualification counts as a missing must-have, exactly once."""
    for gap in gaps:
        same = [
            r
            for r in requirements
            if fuzz.token_set_ratio(r.requirement.lower(), gap.lower()) >= 70
        ]
        for r in same:
            r.result, r.kind = "missing", "must"
        if not same:
            requirements.append(
                RequirementJudgement(
                    requirement=gap,
                    kind="must",
                    result="missing",
                    note="stated requirement not met",
                )
            )


def compute_score(analysis: AnalysisResult, tb: TruthBank, jd_text: str = "") -> FitScore:
    requirements, evidence_flags = verify_judgements(analysis, tb)
    blockers, condition_flags, gaps = _check_conditions(analysis, jd_text)
    _add_gaps(requirements, gaps)
    must = [r for r in requirements if r.kind == "must"]
    nice = [r for r in requirements if r.kind == "nice"]

    if (loc := _location_blocker(analysis, tb)) is not None:
        blockers.append(loc)
    # LLM logistics "blockers" count as concerns; only verified conditions block outright.
    # A licence concern only counts if the JD actually mentions a licence.
    logistics_items = [
        lg
        for lg in analysis.logistics
        if lg.factor != "licence" or not jd_text or _LICENCE.search(jd_text)
    ]
    concerns = sum(1 for lg in logistics_items if lg.status in ("concern", "blocker"))
    concerns += sum(1 for h in analysis.hard_conditions if h.status == "unclear")
    condition_flags += [
        f"{lg.factor}: {lg.note}" for lg in logistics_items if lg.status == "blocker"
    ]
    logistics = max(0.0, WEIGHTS["logistics"] - LOGISTICS_CONCERN_PENALTY * concerns)
    if blockers:
        logistics = 0.0

    breakdown = ScoreBreakdown(
        must=round(WEIGHTS["must"] * _fraction(must), 1),
        experience=round(WEIGHTS["experience"] * _experience_fraction(analysis), 1),
        role=round(WEIGHTS["role"] * FIT_FRACTION[analysis.role_alignment], 1),
        nice=round(WEIGHTS["nice"] * _fraction(nice), 1),
        logistics=round(logistics, 1),
    )
    total = sum(breakdown.model_dump().values())
    if blockers:
        total = min(total, BLOCKER_CAP)
        recommendation: Recommendation = "skip"
    elif total >= APPLY_AT:
        recommendation = "apply"
    elif total >= MAYBE_AT:
        recommendation = "maybe"
    else:
        recommendation = "skip"

    def names(result: str) -> list[str]:
        return [r.requirement for r in requirements if r.result == result]

    return FitScore(
        score=round(total),
        recommendation=recommendation,
        breakdown=breakdown,
        blockers=blockers,
        matched=names("matched"),
        adjacent=names("adjacent"),
        missing=names("missing"),
        red_flags=[*analysis.red_flags, *condition_flags, *evidence_flags],
        summary=analysis.summary[:3],
        requirements=requirements,
    )
