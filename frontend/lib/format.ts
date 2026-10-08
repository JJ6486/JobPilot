import type { ResumeContent, Status } from "@/lib/api";

const dateFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatDate(iso: string | null | undefined): string {
  return iso ? dateFmt.format(new Date(iso)) : "–";
}

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTimeFmt.format(new Date(iso)) : "–";
}

/** "2026-10-11T14:30:44Z" -> "2026-10-11" for <input type="date">, in local time. */
export function toDateInput(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** "2026-10-11" (local) -> ISO string at local noon, so the date doesn't shift across zones. */
export function fromDateInput(value: string): string | null {
  return value ? new Date(`${value}T12:00:00`).toISOString() : null;
}

export function wordCount(text: string): number {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

export const STATUS_LABEL: Record<Status, string> = {
  saved: "Saved",
  tailored: "Tailored",
  applied: "Applied",
  replied: "Replied",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  ghosted: "Ghosted",
  skipped: "Skipped",
  withdrawn: "Withdrawn",
};

export const ROLE_FAMILY_LABEL: Record<string, string> = {
  software_ict: "Software / ICT",
  teaching: "Teaching",
};

/** Plain-text rendering of resume content, in template order, for the diff view. */
export function resumeToLines(r: ResumeContent): string[] {
  const out: string[] = [r.headline, "SUMMARY", r.summary];
  const entries = (title: string, list: ResumeContent["experience"]) => {
    if (!list.length) return;
    out.push(title);
    for (const e of list) {
      out.push([e.heading, e.dates].filter(Boolean).join(" "));
      if (e.title) out.push(e.title);
      out.push(...e.bullets.map((b) => b.text));
    }
  };
  if (r.role_family === "teaching") {
    if (r.teaching_intro.length || r.workshops.length || r.teaching_roles.length) out.push("TEACHING EXPERIENCE");
    out.push(...r.teaching_intro.map((b) => b.text));
    if (r.workshops.length) out.push("Notable Sessions & Workshops", ...r.workshops.map((b) => b.text));
    for (const e of r.teaching_roles) out.push(e.heading, ...e.bullets.map((b) => b.text));
  }
  entries("WORK EXPERIENCE", r.experience);
  entries(r.role_family === "teaching" ? "PROJECTS" : "APPLICATION PROJECTS", r.projects);
  if (r.role_family === "teaching") {
    for (const g of r.skill_groups) out.push(g.label.toUpperCase(), g.skills.join(", "));
  } else if (r.skill_groups.length) {
    out.push("SKILLS", ...r.skill_groups.map((g) => `${g.label}: ${g.skills.join(", ")}`));
  }
  if (r.currently_learning.length) out.push(`Currently learning: ${r.currently_learning.join(", ")}`);
  if (r.achievements.length) {
    out.push("ACHIEVEMENTS");
    for (const a of r.achievements) out.push(`${a.title} ${a.meta}`, a.text);
  }
  if (r.certifications.length) out.push("CERTIFICATIONS", ...r.certifications.map((c) => `${c.name} – ${c.rest}`));
  if (r.leadership.length) out.push("LEADERSHIP AND COMMUNITY CONTRIBUTIONS", ...r.leadership.map((b) => b.text));
  return out.filter((line) => line.trim());
}
