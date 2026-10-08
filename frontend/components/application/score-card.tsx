import { OctagonAlert } from "lucide-react";

import { ScoreBadge } from "@/components/common";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FitScore } from "@/lib/api";
import { cn } from "@/lib/utils";

const PARTS: { key: keyof FitScore["breakdown"]; label: string; max: number }[] = [
  { key: "must", label: "Must-have skills", max: 40 },
  { key: "experience", label: "Experience", max: 20 },
  { key: "role", label: "Role alignment", max: 15 },
  { key: "nice", label: "Nice-to-haves", max: 10 },
  { key: "logistics", label: "Logistics", max: 15 },
];

function Chips({ items, tone }: { items: string[]; tone: "good" | "partial" | "gap" }) {
  if (!items.length) return <p className="text-sm text-muted-foreground">None</p>;
  const cls = {
    good: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
    partial: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
    gap: "bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200",
  }[tone];
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <li key={item} className={cn("rounded-md px-2 py-0.5 text-xs", cls)}>
          {item}
        </li>
      ))}
    </ul>
  );
}

export function ScoreCard({ fit }: { fit: FitScore }) {
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center justify-between gap-2">
          <span>Fit</span>
          <span className="text-2xl">
            <ScoreBadge score={fit.score} recommendation={fit.recommendation} />
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {fit.blockers.length > 0 && (
          <div className="space-y-1 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
            <p className="flex items-center gap-1.5 font-semibold text-destructive">
              <OctagonAlert className="size-4" /> Hard blocker
            </p>
            {fit.blockers.map((b) => (
              <p key={b} className="text-destructive">
                {b}
              </p>
            ))}
          </div>
        )}

        <ul className="space-y-1 text-sm">
          {fit.summary.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>

        <div className="space-y-2">
          {PARTS.map((p) => {
            const value = fit.breakdown[p.key];
            return (
              <div key={p.key} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-muted-foreground">{p.label}</span>
                  <span className="tabular-nums">
                    {value} / {p.max}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className="h-full rounded-full bg-primary" style={{ width: `${(value / p.max) * 100}%` }} />
                </div>
              </div>
            );
          })}
        </div>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <p className="text-xs font-medium uppercase text-muted-foreground">Matched</p>
            <Chips items={fit.matched} tone="good" />
          </div>
          <div className="space-y-1.5">
            <p className="text-xs font-medium uppercase text-muted-foreground">Adjacent (partial credit)</p>
            <Chips items={fit.adjacent} tone="partial" />
          </div>
          <div className="space-y-1.5">
            <p className="text-xs font-medium uppercase text-muted-foreground">Gaps (never put on the resume)</p>
            <Chips items={fit.missing} tone="gap" />
          </div>
        </div>

        {fit.red_flags.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs font-medium uppercase text-muted-foreground">Red flags</p>
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {fit.red_flags.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
