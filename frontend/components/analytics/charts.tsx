"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { AnalyticsSummary, RateRow } from "@/lib/api";

const weekFmt = new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" });
const weekLabel = (iso: string) => weekFmt.format(new Date(`${iso}T00:00:00`));

export function StatTile({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="mt-1 text-3xl font-semibold">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

type TooltipPayload = { name: string; value: number; color: string };

function WeekTooltip({ active, payload, label }: { active?: boolean; payload?: TooltipPayload[]; label?: string }) {
  if (!active || !payload?.length || !label) return null;
  return (
    <div className="rounded-md border bg-popover px-3 py-2 text-sm shadow-md">
      <p className="mb-1 font-medium">Week of {weekLabel(label)}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-2">
          <span className="size-2.5 rounded-sm" style={{ background: p.color }} />
          <span className="text-muted-foreground">{p.name}</span>
          <span className="ml-auto pl-4 font-medium tabular-nums">{p.value}</span>
        </p>
      ))}
    </div>
  );
}

/** Jobs analysed vs applications sent per week (two series, one axis). */
export function WeeklyChart({ data }: { data: AnalyticsSummary["per_week"] }) {
  return (
    <div className="space-y-2">
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }} barGap={2} barCategoryGap="25%">
            <CartesianGrid vertical={false} stroke="var(--viz-grid)" />
            <XAxis
              dataKey="week_start"
              tickFormatter={weekLabel}
              tick={{ fill: "var(--viz-axis)", fontSize: 12 }}
              axisLine={{ stroke: "var(--viz-grid)" }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis allowDecimals={false} tick={{ fill: "var(--viz-axis)", fontSize: 12 }} axisLine={false} tickLine={false} />
            <Tooltip content={<WeekTooltip />} cursor={{ fill: "var(--viz-grid)", opacity: 0.5 }} />
            <Legend
              verticalAlign="top"
              align="right"
              iconType="square"
              iconSize={10}
              wrapperStyle={{ fontSize: 12, paddingBottom: 8 }}
              formatter={(value) => <span className="text-muted-foreground">{value}</span>}
            />
            <Bar dataKey="analysed" name="Analysed" fill="var(--viz-1)" radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
            <Bar dataKey="applied" name="Applied" fill="var(--viz-2)" radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-muted-foreground">Show as table</summary>
        <table className="mt-2 w-full text-left tabular-nums">
          <thead className="text-muted-foreground">
            <tr>
              <th className="py-1 font-normal">Week of</th>
              <th className="py-1 font-normal">Analysed</th>
              <th className="py-1 font-normal">Applied</th>
            </tr>
          </thead>
          <tbody>
            {data.map((w) => (
              <tr key={w.week_start} className="border-t">
                <td className="py-1">{weekLabel(w.week_start)}</td>
                <td className="py-1">{w.analysed}</td>
                <td className="py-1">{w.applied}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

/** Horizontal bar with the value at the tip; the bar is the only coloured element.
 * `stacked` puts the label on its own line (for long labels such as JD requirement text). */
function HBar({
  label,
  value,
  max,
  text,
  stacked = false,
}: {
  label: string;
  value: number;
  max: number;
  text: string;
  stacked?: boolean;
}) {
  const pct = max > 0 ? (value / max) * 100 : 0;
  const bar = (
    <span className="flex min-w-0 items-center gap-2">
      <span className="h-3 min-w-0 flex-1">
        <span
          className="block h-full rounded-r bg-[var(--viz-1)]"
          style={{ width: `${pct}%`, minWidth: value > 0 ? 3 : 0 }}
        />
      </span>
      <span className="shrink-0 text-right text-muted-foreground tabular-nums">{text}</span>
    </span>
  );
  if (stacked)
    return (
      <li className="space-y-1 text-sm">
        <span className="block wrap-break-word">{label}</span>
        {bar}
      </li>
    );
  return (
    <li className="grid grid-cols-[minmax(64px,110px)_minmax(0,1fr)] items-center gap-3 text-sm">
      <span className="truncate" title={label}>
        {label}
      </span>
      {bar}
    </li>
  );
}

const STAGE_LABEL = { applied: "Applied", replied: "Got a reply", interview: "Interview", offer: "Offer" } as const;

export function Funnel({ funnel }: { funnel: AnalyticsSummary["funnel"] }) {
  const top = funnel.applied;
  return (
    <ul className="space-y-2.5">
      {(Object.keys(STAGE_LABEL) as (keyof typeof STAGE_LABEL)[]).map((stage) => {
        const n = funnel[stage];
        const pct = top ? Math.round((n / top) * 100) : 0;
        return <HBar key={stage} label={STAGE_LABEL[stage]} value={n} max={top} text={stage === "applied" ? `${n}` : `${n} (${pct}%)`} />;
      })}
    </ul>
  );
}

export function RateBars({ rows, labels }: { rows: RateRow[]; labels?: Record<string, string> }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">No applications sent yet.</p>;
  return (
    <ul className="space-y-2.5">
      {rows.map((r) => (
        <HBar
          key={r.key}
          label={labels?.[r.key] ?? r.key}
          value={r.rate}
          max={1}
          text={`${r.replied}/${r.applied} · ${Math.round(r.rate * 100)}%`}
        />
      ))}
    </ul>
  );
}

export function CountBars({ rows }: { rows: { skill: string; count: number }[] }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">Nothing yet.</p>;
  const max = Math.max(...rows.map((r) => r.count));
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <HBar key={r.skill} label={r.skill} value={r.count} max={max} text={`${r.count} job${r.count > 1 ? "s" : ""}`} stacked />
      ))}
    </ul>
  );
}
