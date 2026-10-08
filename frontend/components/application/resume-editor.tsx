"use client";

import { ArrowDown, ArrowUp, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ResumeBullet, ResumeContent, ResumeEntry } from "@/lib/api";

type Props = { value: ResumeContent; onChange: (next: ResumeContent) => void };

function move<T>(list: T[], index: number, delta: number): T[] {
  const next = [...list];
  const target = index + delta;
  if (target < 0 || target >= next.length) return list;
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}

/** Edit, reorder or remove bullets. New bullets can't be added here: they must come from the truth bank. */
function BulletList({ bullets, onChange }: { bullets: ResumeBullet[]; onChange: (b: ResumeBullet[]) => void }) {
  return (
    <ul className="space-y-2">
      {bullets.map((b, i) => (
        <li key={`${b.source_id}-${i}`} className="flex gap-2">
          <Textarea
            value={b.text}
            onChange={(e) => onChange(bullets.map((x, j) => (j === i ? { ...x, text: e.target.value } : x)))}
            className="min-h-0 py-1.5 text-sm"
            rows={2}
          />
          <div className="flex shrink-0 flex-col gap-1">
            <Button variant="ghost" size="icon" className="size-7" aria-label="Move up" onClick={() => onChange(move(bullets, i, -1))} disabled={i === 0}>
              <ArrowUp className="size-3.5" />
            </Button>
            <Button variant="ghost" size="icon" className="size-7" aria-label="Move down" onClick={() => onChange(move(bullets, i, 1))} disabled={i === bullets.length - 1}>
              <ArrowDown className="size-3.5" />
            </Button>
            <Button variant="ghost" size="icon" className="size-7 text-muted-foreground hover:text-destructive" aria-label="Remove bullet" onClick={() => onChange(bullets.filter((_, j) => j !== i))}>
              <Trash2 className="size-3.5" />
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}

function Entries({
  title,
  entries,
  onChange,
}: {
  title: string;
  entries: ResumeEntry[];
  onChange: (e: ResumeEntry[]) => void;
}) {
  if (!entries.length) return null;
  return (
    <section className="space-y-3">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      {entries.map((entry, i) => (
        <div key={entry.source_id} className="space-y-2 rounded-lg border p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <p className="font-medium">
                {entry.heading} {entry.dates && <span className="font-normal text-muted-foreground">{entry.dates}</span>}
              </p>
              {entry.title && <p className="text-sm italic text-muted-foreground">{entry.title}</p>}
            </div>
            <div className="flex gap-1">
              <Button variant="ghost" size="icon" className="size-7" aria-label="Move entry up" onClick={() => onChange(move(entries, i, -1))} disabled={i === 0}>
                <ArrowUp className="size-3.5" />
              </Button>
              <Button variant="ghost" size="icon" className="size-7" aria-label="Move entry down" onClick={() => onChange(move(entries, i, 1))} disabled={i === entries.length - 1}>
                <ArrowDown className="size-3.5" />
              </Button>
              <Button variant="ghost" size="icon" className="size-7 text-muted-foreground hover:text-destructive" aria-label="Remove entry" onClick={() => onChange(entries.filter((_, j) => j !== i))}>
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          </div>
          <BulletList
            bullets={entry.bullets}
            onChange={(bullets) => onChange(entries.map((e, j) => (j === i ? { ...e, bullets } : e)))}
          />
        </div>
      ))}
    </section>
  );
}

function Bullets({ title, bullets, onChange }: { title: string; bullets: ResumeBullet[]; onChange: (b: ResumeBullet[]) => void }) {
  if (!bullets.length) return null;
  return (
    <section className="space-y-2">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
      <BulletList bullets={bullets} onChange={onChange} />
    </section>
  );
}

const splitList = (text: string) =>
  text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

export function ResumeEditor({ value, onChange }: Props) {
  const set = <K extends keyof ResumeContent>(key: K, v: ResumeContent[K]) => onChange({ ...value, [key]: v });
  const teaching = value.role_family === "teaching";

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        Company names, titles and dates come from your truth bank and can&apos;t be edited here. Edit wording,
        reorder or remove bullets; the validator re-checks everything when you save.
      </p>
      <div className="space-y-2">
        <Label htmlFor="headline">Headline</Label>
        <Input id="headline" value={value.headline} onChange={(e) => set("headline", e.target.value)} />
      </div>
      <div className="space-y-2">
        <Label htmlFor="summary">Summary</Label>
        <Textarea id="summary" value={value.summary} onChange={(e) => set("summary", e.target.value)} rows={5} />
      </div>

      {teaching && <Bullets title="Teaching experience" bullets={value.teaching_intro} onChange={(b) => set("teaching_intro", b)} />}
      {teaching && <Bullets title="Notable sessions & workshops" bullets={value.workshops} onChange={(b) => set("workshops", b)} />}
      {teaching && <Entries title="Teaching roles" entries={value.teaching_roles} onChange={(e) => set("teaching_roles", e)} />}
      <Entries title="Work experience" entries={value.experience} onChange={(e) => set("experience", e)} />
      <Entries title="Projects" entries={value.projects} onChange={(e) => set("projects", e)} />

      <section className="space-y-3">
        <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Skills</h3>
        {value.skill_groups.map((g, i) => (
          // keyed by content so the uncontrolled skills input resets after regenerate/undo
          <div key={`${i}:${g.skills.join(",")}`} className="grid gap-2 sm:grid-cols-[200px_1fr_auto]">
            <Input
              value={g.label}
              aria-label="Group label"
              onChange={(e) => set("skill_groups", value.skill_groups.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)))}
            />
            <Input
              defaultValue={g.skills.join(", ")}
              aria-label="Skills (comma-separated)"
              onBlur={(e) => set("skill_groups", value.skill_groups.map((x, j) => (j === i ? { ...x, skills: splitList(e.target.value) } : x)))}
            />
            <Button variant="ghost" size="icon" aria-label="Remove group" onClick={() => set("skill_groups", value.skill_groups.filter((_, j) => j !== i))}>
              <Trash2 className="size-4" />
            </Button>
          </div>
        ))}
        {value.currently_learning.length > 0 && (
          <div className="space-y-1">
            <Label>Currently learning</Label>
            <Input key={value.currently_learning.join(",")} defaultValue={value.currently_learning.join(", ")} onBlur={(e) => set("currently_learning", splitList(e.target.value))} />
          </div>
        )}
      </section>

      {value.achievements.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Achievements</h3>
          {value.achievements.map((a, i) => (
            <div key={a.source_id} className="flex items-start justify-between gap-2 rounded-lg border p-3 text-sm">
              <div>
                <p className="font-medium">
                  {a.title} <span className="font-normal text-muted-foreground">{a.meta}</span>
                </p>
                <p>{a.text}</p>
              </div>
              <Button variant="ghost" size="icon" className="size-7" aria-label="Remove achievement" onClick={() => set("achievements", value.achievements.filter((_, j) => j !== i))}>
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          ))}
        </section>
      )}

      {value.certifications.length > 0 && (
        <section className="space-y-2">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Certifications</h3>
          {value.certifications.map((c, i) => (
            <div key={c.source_id} className="flex items-center justify-between gap-2 text-sm">
              <span>
                {c.name} <span className="text-muted-foreground">– {c.rest}</span>
              </span>
              <Button variant="ghost" size="icon" className="size-7" aria-label="Remove certification" onClick={() => set("certifications", value.certifications.filter((_, j) => j !== i))}>
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          ))}
        </section>
      )}

      <Bullets title="Leadership & community" bullets={value.leadership} onChange={(b) => set("leadership", b)} />
    </div>
  );
}
