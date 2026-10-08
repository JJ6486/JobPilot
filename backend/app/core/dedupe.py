"""Duplicate detection: same (company, title, city), same canonical URL, or similar JD text."""

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel
from rapidfuzz import fuzz

TEXT_SIMILARITY_THRESHOLD = 90
_TRACKING_PARAMS = re.compile(r"^(utm_|fbclid|gclid|ref|refid|trk|src|source|from)", re.I)
_COMPANY_SUFFIXES = re.compile(r"\b(llc|ltd|limited|inc|co|company|corp|est|group|pvt)\b\.?", re.I)


class JobRecord(BaseModel):
    id: str
    company: str
    title: str
    city: str = ""
    url: str = ""
    jd_text: str
    status: str = ""
    applied_at: str | None = None
    created_at: str = ""


class DuplicateMatch(BaseModel):
    job_id: str
    company: str
    title: str
    reasons: list[str]
    similarity: int
    status: str
    applied_at: str | None
    created_at: str


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9؀-ۿ]+", " ", text.lower()).split())


def job_key(company: str, title: str, city: str) -> str:
    company = _norm(_COMPANY_SUFFIXES.sub("", company))
    raw = "|".join([company, _norm(title), _norm(city)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def canonical_url(url: str) -> str:
    if not url.strip():
        return ""
    parts = urlsplit(url.strip())
    query = [(k, v) for k, v in parse_qsl(parts.query) if not _TRACKING_PARAMS.match(k)]
    host = parts.netloc.lower().removeprefix("www.")
    return urlunsplit(("https", host, parts.path.rstrip("/"), urlencode(sorted(query)), ""))


def find_duplicates(new: JobRecord, existing: list[JobRecord]) -> list[DuplicateMatch]:
    new_key = job_key(new.company, new.title, new.city)
    new_url = canonical_url(new.url)
    new_text = _norm(new.jd_text)
    matches: list[DuplicateMatch] = []
    for old in existing:
        if old.id == new.id:
            continue
        reasons: list[str] = []
        if new.company and new.title and job_key(old.company, old.title, old.city) == new_key:
            reasons.append("same company, title and city")
        if new_url and canonical_url(old.url) == new_url:
            reasons.append("same job URL")
        similarity = round(fuzz.token_set_ratio(new_text, _norm(old.jd_text)))
        if similarity >= TEXT_SIMILARITY_THRESHOLD:
            reasons.append(f"JD text {similarity}% similar")
        if reasons:
            matches.append(
                DuplicateMatch(
                    job_id=old.id,
                    company=old.company,
                    title=old.title,
                    reasons=reasons,
                    similarity=similarity,
                    status=old.status,
                    applied_at=old.applied_at,
                    created_at=old.created_at,
                )
            )
    return sorted(matches, key=lambda m: -m.similarity)
