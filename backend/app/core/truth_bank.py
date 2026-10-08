"""Load, validate, and expose the truth bank (data/truth_bank.yaml).

The truth bank is the single source of truth about the candidate. Everything the LLM may
say about them has to trace back to an id in here. `llm_view()` returns the copy that is
safe to send to an LLM: no `profile` block and no `*_local_only` fields.
"""

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

RoleFamily = Literal["software_ict", "teaching"]
SkillLevel = Literal["core", "project", "learning"]


class _Model(BaseModel):
    # Unknown keys are errors so typos ("evidance:") don't silently disappear.
    model_config = ConfigDict(extra="forbid")


class Links(_Model):
    linkedin: str = ""
    github: str = ""
    portfolio: str = ""


class Profile(_Model):
    full_name: str
    email: str
    phone: str
    location: str
    phone_display: str = ""
    location_display: str = ""
    links: Links = Links()


class Language(_Model):
    name: str
    level: str


class Constraints(_Model):
    current_country: str
    visa_status: str
    can_transfer_iqama: bool
    nationality: str
    accepted_cities: list[str]
    open_to_relocation: bool
    open_to_remote: bool
    teaching_licence: str
    languages: list[Language]
    min_salary_sar: int | None = None
    earliest_start: str = ""


class SummaryOption(_Model):
    id: str
    text: str


class RoleFamilyConfig(_Model):
    base_resume: str
    template: str
    headline: str
    motivation: str = ""  # why this kind of role; used in cover letters
    summary_options: list[SummaryOption] = Field(min_length=1)


class Bullet(_Model):
    id: str
    text: str
    skills: list[str] = []
    tags: list[str] = []


class Experience(_Model):
    id: str
    kind: Literal["work", "activity"]
    company: str
    short_name: str = ""
    title: str
    location: str = ""
    start: str
    end: str
    role_families: list[RoleFamily]
    bullets: list[Bullet] = Field(min_length=1)


class Workshop(_Model):
    id: str
    title: str
    event: str
    year: str = ""
    text: str
    skills: list[str] = []


class Project(_Model):
    id: str
    name: str
    description: str
    url: str = ""
    urls: list[str] = []
    status: str = ""
    context: str = ""
    role_families: list[RoleFamily]
    bullets: list[Bullet] = Field(min_length=1)


class Achievement(_Model):
    id: str
    title: str
    issuer: str = ""
    year: str = ""
    text: str
    evidence: list[str] = []
    section: Literal["achievements", "leadership"] = "achievements"


class Education(_Model):
    id: str
    institution: str
    degree: str
    field: str = ""
    start: str
    end: str
    notes: str = ""


class Certification(_Model):
    id: str
    name: str
    issuer: str
    year: str = ""
    detail: str = ""
    credential_id_local_only: str = ""
    url_local_only: str = ""


class Skill(_Model):
    name: str
    level: SkillLevel
    years: float | None = None
    evidence: list[str] = []
    aliases: list[str] = []
    adjacent_to: list[str] = []


class WritingPreferences(_Model):
    tone: str = "professional, warm, concise"
    avoid_phrases: list[str] = []


class TruthBank(_Model):
    profile: Profile
    constraints: Constraints
    role_families: dict[RoleFamily, RoleFamilyConfig]
    experience: list[Experience]
    workshops: list[Workshop] = []
    projects: list[Project] = []
    achievements: list[Achievement] = []
    education: list[Education]
    certifications: list[Certification] = []
    skills: list[Skill]
    never_claim: list[str] = []
    writing_preferences: WritingPreferences = WritingPreferences()

    @model_validator(mode="after")
    def _check_references(self) -> "TruthBank":
        problems: list[str] = []
        seen: dict[str, str] = {}
        for id_, where in self._all_ids():
            if id_ in seen:
                problems.append(f"duplicate id {id_!r} ({seen[id_]} and {where})")
            seen[id_] = where

        known_skills = {self._norm(n) for s in self.skills for n in [s.name, *s.aliases]}
        seen_names: set[str] = set()
        for i, s in enumerate(self.skills):
            if self._norm(s.name) in seen_names:
                problems.append(f"skills[{i}]: duplicate skill name {s.name!r}")
            seen_names.add(self._norm(s.name))
            for ev in s.evidence:
                if ev not in seen:
                    problems.append(f"skills[{i}] ({s.name}).evidence: unknown id {ev!r}")
        for a_i, a in enumerate(self.achievements):
            for ev in a.evidence:
                if ev not in seen:
                    problems.append(f"achievements[{a_i}].evidence: unknown id {ev!r}")
        for bullet, where in self._all_bullets():
            for name in bullet.skills:
                if self._norm(name) not in known_skills:
                    problems.append(f"{where}.skills: {name!r} is not in the skills list")
        if problems:
            raise ValueError("; ".join(problems))
        return self

    # ---- lookups ------------------------------------------------------------------

    @staticmethod
    def _norm(name: str) -> str:
        return " ".join(name.lower().split())

    def _all_ids(self) -> Iterator[tuple[str, str]]:
        for fam, cfg in self.role_families.items():
            for s in cfg.summary_options:
                yield s.id, f"role_families.{fam}"
        for e in self.experience:
            yield e.id, "experience"
            for b in e.bullets:
                yield b.id, f"experience.{e.id}"
        for p in self.projects:
            yield p.id, "projects"
            for b in p.bullets:
                yield b.id, f"projects.{p.id}"
        for group, items in (
            ("workshops", self.workshops),
            ("achievements", self.achievements),
            ("education", self.education),
            ("certifications", self.certifications),
        ):
            for item in items:
                yield item.id, group

    def _all_bullets(self) -> Iterator[tuple[Bullet, str]]:
        for e in self.experience:
            for b in e.bullets:
                yield b, f"experience.{e.id}.{b.id}"
        for p in self.projects:
            for b in p.bullets:
                yield b, f"projects.{p.id}.{b.id}"

    def experience_by_id(self) -> dict[str, Experience]:
        return {e.id: e for e in self.experience}

    def project_by_id(self) -> dict[str, Project]:
        return {p.id: p for p in self.projects}

    def bullet_by_id(self) -> dict[str, Bullet]:
        return {b.id: b for b, _ in self._all_bullets()}

    def all_ids(self) -> set[str]:
        return {id_ for id_, _ in self._all_ids()}

    def find_skill(self, name: str) -> Skill | None:
        """Match a skill by name or alias, case-insensitively."""
        key = self._norm(name)
        for s in self.skills:
            if key == self._norm(s.name) or key in {self._norm(a) for a in s.aliases}:
                return s
        return None

    def text_corpus(self) -> str:
        """Every piece of factual text in the bank (incl. profile), for the validator."""
        return json.dumps(self.model_dump(mode="json"), ensure_ascii=False)

    # ---- LLM-safe view --------------------------------------------------------------

    def llm_view(self) -> dict[str, Any]:
        """The bank minus PII: no profile, no *_local_only fields, no links."""
        data = self.model_dump(mode="json", exclude={"profile"})
        data["constraints"].pop("min_salary_sar", None)
        for fam in data["role_families"].values():
            fam.pop("base_resume", None)
            fam.pop("template", None)
        for p in data["projects"]:
            p.pop("url", None)
            p.pop("urls", None)
        return _strip_local_only(data)

    def content_hash(self) -> str:
        raw = json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _strip_local_only(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _strip_local_only(v) for k, v in value.items() if not k.endswith("_local_only")}
    if isinstance(value, list):
        return [_strip_local_only(v) for v in value]
    return value


class TruthBankError(Exception):
    """Raised with a human-readable list of problems, each pointing at a field."""

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("Truth bank is invalid:\n" + "\n".join(f"  - {p}" for p in problems))


def _find_placeholders(value: Any, path: str = "") -> Iterator[str]:
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _find_placeholders(v, f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _find_placeholders(v, f"{path}[{i}]")
    elif isinstance(value, str) and "<<" in value:
        yield f"{path}: still contains a <<placeholder>> ({value[:60]!r})"


def parse_truth_bank(data: Any) -> TruthBank:
    if not isinstance(data, dict):
        raise TruthBankError(["top level must be a mapping"])
    placeholders = list(_find_placeholders(data))
    if placeholders:
        raise TruthBankError(placeholders)
    try:
        return TruthBank.model_validate(data)
    except ValidationError as exc:
        problems: list[str] = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err["loc"])
            msg = err["msg"].removeprefix("Value error, ")
            if not loc:  # model-level validator: already "field: message"; split them
                problems.extend(msg.split("; "))
            else:
                problems.append(f"{loc}: {msg}")
        raise TruthBankError(problems) from None


def load_truth_bank(path: Path) -> TruthBank:
    if not path.is_file():
        raise TruthBankError([f"file not found: {path}"])
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TruthBankError([f"YAML syntax error: {exc}"]) from None
    return parse_truth_bank(data)
