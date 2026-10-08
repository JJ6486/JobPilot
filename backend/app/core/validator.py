"""Honesty guardrail: scan generated resume and messages for claims the truth bank doesn't support.

Checks, in order of seriousness:
- high: a technology, tool or credential that isn't in the truth bank, a never_claim item,
  a number that doesn't appear in the truth bank, or a reworded bullet that gained a tool or
  number its source bullet doesn't have.
- medium: an "adjacent" tool mentioned in the messages (fine only if phrased as willingness
  to learn), unknown acronyms/CamelCase names, length limits, and avoided phrases.

High-severity warnings block Download until fixed or explicitly confirmed by the user.
"""

import re
from typing import Literal

from pydantic import BaseModel
from rapidfuzz import fuzz

from app.core.resume import ResumeContent
from app.core.tech_terms import ACRONYM_ALLOWLIST, AMBIGUOUS_TERMS, CREDENTIAL_TERMS, TECH_TERMS
from app.core.truth_bank import TruthBank

Severity = Literal["high", "medium"]

LIMITS = {"cover_letter": (100, 200), "email_body": (0, 100), "whatsapp_message": (0, 60)}
NEVER_CLAIM_SIMILARITY = 85
_NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])")
_CAPS_TOKEN = re.compile(r"\b(?:[A-Z]{2,}[A-Za-z0-9]*|[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*|\w+\.js)\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")
_LEARNING_INTENT = re.compile(
    r"\b(learn(ing)?|pick(ing)? up|expand(ing)? (my|into)|explor(e|ing)|eager to|keen to|"
    r"grow(ing)? into|upskill|comfortable (picking|learning|getting)|master(ing)?|"
    r"ramp(ing)? up|get(ting)? up to speed|adapt(ing)? (quickly )?to)\b",
    re.I,
)


class ValidationWarning(BaseModel):
    severity: Severity
    location: str
    text: str
    message: str


class ValidationReport(BaseModel):
    warnings: list[ValidationWarning]

    @property
    def has_high(self) -> bool:
        return any(w.severity == "high" for w in self.warnings)


def _term_pattern(term: str) -> re.Pattern[str]:
    flags = 0 if term in AMBIGUOUS_TERMS else re.IGNORECASE
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9+#])", flags)


_TECH_PATTERNS = [(t, _term_pattern(t)) for t in TECH_TERMS]
_CREDENTIAL_PATTERNS = [(t, _term_pattern(t)) for t in CREDENTIAL_TERMS]


class Validator:
    def __init__(self, tb: TruthBank, allowed_extra: list[str] | None = None) -> None:
        self.tb = tb
        data = tb.model_dump(mode="json", exclude={"never_claim", "writing_preferences"})
        for skill in data["skills"]:
            skill.pop("adjacent_to")  # adjacent tools are exactly what the candidate lacks
        self.corpus = _flatten(data).lower()
        self.extra = " ".join(allowed_extra or []).lower()
        self.numbers = set(_NUMBER.findall(self.corpus))
        self.adjacent = {a.lower() for s in tb.skills for a in s.adjacent_to}
        self.bullets = tb.bullet_by_id()
        self.tool_terms = sorted(
            {*TECH_TERMS, *(n for sk in tb.skills for n in [sk.name, *sk.aliases])}
        )
        # For each bullet: everything its job/project records (bullet texts + tagged skills).
        self.entry_context: dict[str, str] = {}
        for entry in [*tb.experience, *tb.projects]:
            parts = [b.text for b in entry.bullets] + [sk for b in entry.bullets for sk in b.skills]
            context = " | ".join(parts)
            for b in entry.bullets:
                self.entry_context[b.id] = context

    # ---- helpers --------------------------------------------------------------------

    def _supported(self, term: str) -> bool:
        if self.tb.find_skill(term) is not None:
            return True
        pattern = re.compile(rf"(?<![a-z0-9]){re.escape(term.lower())}(?![a-z0-9])")
        return bool(pattern.search(self.corpus) or pattern.search(self.extra))

    def _check_text(self, location: str, text: str, is_letter: bool) -> list[ValidationWarning]:
        out: list[ValidationWarning] = []

        def warn(sev: Severity, snippet: str, msg: str) -> None:
            out.append(
                ValidationWarning(severity=sev, location=location, text=snippet, message=msg)
            )

        for term, pattern in _TECH_PATTERNS:
            if not pattern.search(text) or self._supported(term):
                continue
            if not is_letter:
                if term.lower() in self.adjacent:
                    msg = f"'{term}' is only adjacent to your skills; keep it off the resume."
                else:
                    msg = f"'{term}' isn't in your truth bank; keep it off the resume."
                warn("high", term, msg)
            elif _in_learning_sentence(text, pattern):
                warn(
                    "medium",
                    term,
                    f"'{term}' isn't in your truth bank; it's mentioned as something to learn. "
                    "Check the wording doesn't read as a claim.",
                )
            else:
                warn("high", term, f"'{term}' is not in your truth bank.")
        for term, pattern in _CREDENTIAL_PATTERNS:
            if pattern.search(text) and not self._supported(term):
                warn("high", term, f"Credential '{term}' is not in your truth bank.")

        for item in self.tb.never_claim:
            core = re.sub(r"\(.*?\)", "", item).strip()
            for sentence in _SENTENCE.split(text):
                if (
                    sentence
                    and fuzz.partial_ratio(core.lower(), sentence.lower()) >= NEVER_CLAIM_SIMILARITY
                ):
                    warn(
                        "high", sentence.strip()[:120], f"Looks like a never_claim item: {item!r}."
                    )
                    break

        for number in set(_NUMBER.findall(text)):
            if number not in self.numbers:
                warn(
                    "high",
                    number,
                    f"The number {number} doesn't appear anywhere in your truth bank.",
                )

        known_terms = {t.lower() for t in TECH_TERMS + CREDENTIAL_TERMS}
        for token in set(_CAPS_TOKEN.findall(text)):
            if token in ACRONYM_ALLOWLIST or token.lower() in known_terms:
                continue
            if not self._supported(token):
                warn(
                    "medium", token, f"'{token}' isn't in your truth bank. Check it's not a claim."
                )
        return out

    def _check_bullet_drift(
        self, location: str, text: str, source_id: str
    ) -> list[ValidationWarning]:
        """A reworded bullet may not gain numbers its source lacks, or tools that weren't used in
        that job/project. Tools tagged on the bullet (its `skills`) or used anywhere in the same
        entry are fine: naming them states a fact the truth bank already records for that role."""
        source = self.bullets.get(source_id)
        if source is None or " ".join(text.split()) == " ".join(source.text.split()):
            return []
        out: list[ValidationWarning] = []
        for number in sorted(set(_NUMBER.findall(text)) - set(_NUMBER.findall(source.text))):
            out.append(
                ValidationWarning(
                    severity="high",
                    location=location,
                    text=number,
                    message=f"The rewording added the number {number}; the original bullet "
                    f"({source_id}) doesn't have it.",
                )
            )
        allowed = self.entry_context.get(source_id, source.text)
        for name in self._tools_in(text):
            if not _term_pattern(name).search(allowed) and not any(
                _term_pattern(alias).search(allowed) for alias in self._aliases(name)
            ):
                out.append(
                    ValidationWarning(
                        severity="high",
                        location=location,
                        text=name,
                        message=f"The rewording added '{name}', but your truth bank doesn't link "
                        f"it to this job or project ({source_id}).",
                    )
                )
        return out

    def _aliases(self, name: str) -> list[str]:
        skill = self.tb.find_skill(name)
        return [skill.name, *skill.aliases] if skill else [name]

    def _tools_in(self, text: str) -> list[str]:
        """Tool names in `text`, each once under its canonical skill name. A match inside a
        longer match is ignored ("Next" inside "Next.js", "Spring" inside "Spring Boot")."""
        spans: list[tuple[int, int, str]] = []
        for term in self.tool_terms:
            spans += [(m.start(), m.end(), term) for m in _term_pattern(term).finditer(text)]
        spans.sort(key=lambda s: (s[0] - s[1], s[0]))  # longest first
        taken: list[tuple[int, int]] = []
        names: list[str] = []
        for start, end, term in spans:
            if any(start >= a and end <= b for a, b in taken):
                continue
            taken.append((start, end))
            skill = self.tb.find_skill(term)
            name = skill.name if skill else term
            if name not in names:
                names.append(name)
        return names

    # ---- public ---------------------------------------------------------------------

    def validate(self, resume: ResumeContent, letters: dict[str, str]) -> ValidationReport:
        warnings: list[ValidationWarning] = []
        bullet_ids = set(self.bullets)
        for where, text, source_id in resume.all_text():
            warnings += self._check_text(f"resume {where}", text, is_letter=False)
            if source_id in bullet_ids:
                warnings += self._check_bullet_drift(f"resume {where}", text, source_id)

        avoid = [p.lower() for p in self.tb.writing_preferences.avoid_phrases]
        for name, text in letters.items():
            warnings += self._check_text(name, text, is_letter=True)
            lo, hi = LIMITS.get(name, (0, 10_000))
            words = len(text.split())
            if not lo <= words <= hi:
                warnings.append(
                    ValidationWarning(
                        severity="medium",
                        location=name,
                        text=f"{words} words",
                        message=f"Should be {lo}-{hi} words.",
                    )
                )
            for phrase in avoid:
                if phrase in text.lower():
                    warnings.append(
                        ValidationWarning(
                            severity="medium",
                            location=name,
                            text=phrase,
                            message=f"Uses an avoided phrase: '{phrase}'.",
                        )
                    )
        return ValidationReport(warnings=_dedupe(warnings))


def _in_learning_sentence(text: str, pattern: re.Pattern[str]) -> bool:
    """True if every sentence mentioning the term frames it as something to learn."""
    sentences = [s for s in _SENTENCE.split(text) if pattern.search(s)]
    return bool(sentences) and all(_LEARNING_INTENT.search(s) for s in sentences)


def _flatten(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(v) for v in value)
    return str(value)


def _dedupe(warnings: list[ValidationWarning]) -> list[ValidationWarning]:
    seen: set[tuple[str, str, str]] = set()
    out: list[ValidationWarning] = []
    for w in sorted(warnings, key=lambda w: w.severity != "high"):
        key = (w.severity, w.location, w.text.lower())
        if key not in seen:
            seen.add(key)
            out.append(w)
    return out
