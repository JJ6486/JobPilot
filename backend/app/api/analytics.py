"""Analytics computed from the tracker data (no LLM calls)."""

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter
from pydantic import BaseModel
from sqlmodel import col, select

from app.db.models import Application, Event, Job, JobRequirement, now
from app.db.repository import REPLIED_STATUSES, follow_up_due, suggest_ghosted
from app.db.session import SessionDep

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Funnel stages, in order. A later stage implies the earlier ones.
STAGES = ["applied", "replied", "interview", "offer"]
STAGE_OF = {
    "applied": 0,
    "ghosted": 0,
    "withdrawn": 0,
    "replied": 1,
    "rejected": 1,
    "interview": 2,
    "offer": 3,
}
SCORE_BANDS = [("0-44", 0, 44), ("45-69", 45, 69), ("70-100", 70, 100)]
WEEKS = 12


class WeekCount(BaseModel):
    week_start: str
    analysed: int
    applied: int


class RateRow(BaseModel):
    key: str
    applied: int
    replied: int
    rate: float  # 0..1


class Summary(BaseModel):
    total: int
    by_status: dict[str, int]
    follow_ups_due: int
    ghost_suggestions: int
    per_week: list[WeekCount]
    funnel: dict[str, int]
    response_by_portal: list[RateRow]
    response_by_role_family: list[RateRow]
    response_by_resume_variant: list[RateRow]
    response_by_score_band: list[RateRow]
    median_days_to_first_reply: float | None


class SkillGap(BaseModel):
    skill: str
    count: int


class SkillGaps(BaseModel):
    jobs_analysed: int
    missing: list[SkillGap]
    adjacent: list[SkillGap]


def _week(d: datetime) -> str:
    return (d.date() - timedelta(days=d.weekday())).isoformat()  # Monday


def _rates(groups: dict[str, list[bool]]) -> list[RateRow]:
    rows = [
        RateRow(key=k or "(none)", applied=len(v), replied=sum(v), rate=round(sum(v) / len(v), 3))
        for k, v in groups.items()
        if v
    ]
    return sorted(rows, key=lambda r: (-r.applied, r.key))


@router.get("/summary", response_model=Summary)
def summary(session: SessionDep) -> Summary:
    rows = session.exec(
        select(Application, Job).join(Job, col(Job.id) == col(Application.job_id))
    ).all()
    events = session.exec(
        select(Event).where(Event.type == "status_change").order_by(col(Event.created_at))
    ).all()
    reached: dict[int, int] = defaultdict(lambda: -1)  # furthest stage index per application
    first_reply: dict[int, datetime] = {}
    for e in events:
        stage = STAGE_OF.get(e.to_status or "", -1)
        reached[e.application_id] = max(reached[e.application_id], stage)
        if e.to_status in REPLIED_STATUSES and e.application_id not in first_reply:
            first_reply[e.application_id] = e.created_at

    today = now()
    weeks = [_week(today - timedelta(weeks=i)) for i in reversed(range(WEEKS))]
    analysed, applied_weeks = Counter[str](), Counter[str]()
    funnel = dict.fromkeys(STAGES, 0)
    by_portal, by_family, by_variant, by_band = (defaultdict(list) for _ in range(4))
    reply_days: list[float] = []
    for app, job in rows:
        assert app.id is not None
        analysed[_week(app.created_at)] += 1
        stage = max(reached[app.id], STAGE_OF.get(app.status, -1))
        if app.applied_at is None and stage < 0:
            continue  # never applied: not part of response rates
        if app.applied_at:
            applied_weeks[_week(app.applied_at)] += 1
        for i, name in enumerate(STAGES):
            funnel[name] += stage >= i
        replied = stage >= 1
        by_portal[job.source_portal.strip().lower()].append(replied)
        by_family[job.role_family].append(replied)
        by_variant[app.resume_variant].append(replied)
        band = next(name for name, lo, hi in SCORE_BANDS if lo <= app.fit_score <= hi)
        by_band[band].append(replied)
        if app.applied_at and app.id in first_reply:
            reply_days.append((first_reply[app.id] - app.applied_at).total_seconds() / 86400)

    return Summary(
        total=len(rows),
        by_status=dict(Counter(app.status for app, _ in rows)),
        follow_ups_due=sum(1 for app, _ in rows if follow_up_due(app)),
        ghost_suggestions=sum(1 for app, _ in rows if suggest_ghosted(app)),
        per_week=[
            WeekCount(week_start=w, analysed=analysed[w], applied=applied_weeks[w]) for w in weeks
        ],
        funnel=funnel,
        response_by_portal=_rates(by_portal),
        response_by_role_family=_rates(by_family),
        response_by_resume_variant=_rates(by_variant),
        response_by_score_band=_rates(by_band),
        median_days_to_first_reply=round(statistics.median(reply_days), 1) if reply_days else None,
    )


@router.get("/skill-gaps", response_model=SkillGaps)
def skill_gaps(session: SessionDep, limit: int = 20) -> SkillGaps:
    reqs = session.exec(select(JobRequirement)).all()
    names: dict[str, str] = {}  # normalized -> first spelling seen

    def tally(result: str) -> list[SkillGap]:
        counts: Counter[str] = Counter()
        for r in reqs:
            if r.result == result:
                key = " ".join(r.skill.lower().split())
                names.setdefault(key, r.skill)
                counts[key] += 1
        return [SkillGap(skill=names[k], count=c) for k, c in counts.most_common(limit)]

    return SkillGaps(
        jobs_analysed=len({r.job_id for r in reqs}),
        missing=tally("missing"),
        adjacent=tally("adjacent"),
    )
