"""The structured, editable resume content. This is what the Review screen edits and what
`render_docx` turns into a file; re-rendering it never calls the LLM.

Every bullet keeps the truth-bank `source_id` it came from, so the validator can compare an
edited or reworded bullet against its source.
"""

from pydantic import BaseModel

from app.core.truth_bank import RoleFamily


class ResumeBullet(BaseModel):
    source_id: str
    text: str


class ResumeEntry(BaseModel):
    source_id: str
    heading: str  # "Company, City" for jobs, "Title – Org" for teaching roles, name for projects
    title: str = ""
    dates: str = ""
    bullets: list[ResumeBullet]


class ResumeSkillGroup(BaseModel):
    label: str
    skills: list[str]


class ResumeAchievement(BaseModel):
    source_id: str
    title: str
    meta: str
    text: str


class ResumeCertification(BaseModel):
    source_id: str
    name: str
    rest: str  # " – <rest>" after the (linked) name


class ResumeContent(BaseModel):
    role_family: RoleFamily
    headline: str
    summary: str
    experience: list[ResumeEntry] = []
    teaching_intro: list[ResumeBullet] = []
    teaching_roles: list[ResumeEntry] = []
    workshops: list[ResumeBullet] = []
    projects: list[ResumeEntry] = []
    skill_groups: list[ResumeSkillGroup] = []
    currently_learning: list[str] = []
    achievements: list[ResumeAchievement] = []
    certifications: list[ResumeCertification] = []
    leadership: list[ResumeBullet] = []

    def all_text(self) -> list[tuple[str, str, str | None]]:
        """(location, text, source_id) for every piece of visible text, for the validator."""
        items: list[tuple[str, str, str | None]] = [
            ("headline", self.headline, None),
            ("summary", self.summary, None),
        ]
        for group, entries in (
            ("experience", self.experience),
            ("teaching role", self.teaching_roles),
            ("project", self.projects),
        ):
            for e in entries:
                items.append((f"{group} heading", e.heading, e.source_id))
                items.append((f"{group} title", e.title, e.source_id))
                items += [(f"{group} bullet", b.text, b.source_id) for b in e.bullets]
        for group, bullets in (
            ("teaching bullet", self.teaching_intro),
            ("workshop", self.workshops),
            ("leadership", self.leadership),
        ):
            items += [(group, b.text, b.source_id) for b in bullets]
        for g in self.skill_groups:
            items.append(("skills label", g.label, None))
            items += [("skill", s, None) for s in g.skills]
        items += [("currently learning", s, None) for s in self.currently_learning]
        for a in self.achievements:
            items += [("achievement", a.title, a.source_id), ("achievement", a.text, a.source_id)]
        for c in self.certifications:
            items.append(("certification", f"{c.name} – {c.rest}", c.source_id))
        return [(where, text, sid) for where, text, sid in items if text]
