"use client";

import { BellRing, Download, Ghost, LayoutGrid, Plus, Rows3, X } from "lucide-react";
import Link from "next/link";
import { useState, useSyncExternalStore } from "react";
import { toast } from "sonner";

import { EmptyState, ErrorState, PageHeader } from "@/components/common";
import { ApplicationsTable } from "@/components/tracker/applications-table";
import { KanbanBoard } from "@/components/tracker/kanban-board";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, ApiError, CHANNELS, PORTALS, STATUSES, type ListFilters, type Status } from "@/lib/api";
import { fromDateInput, ROLE_FAMILY_LABEL, STATUS_LABEL } from "@/lib/format";
import { useAsync } from "@/lib/hooks";

const ALL = "__all__";
const VIEW_KEY = "jobpilot.tracker.view";

type FilterState = {
  q: string;
  status: string;
  portal: string;
  role_family: string;
  channel: string;
  score_min: string;
  score_max: string;
  date_from: string;
  date_to: string;
};
const EMPTY: FilterState = {
  q: "",
  status: ALL,
  portal: ALL,
  role_family: ALL,
  channel: ALL,
  score_min: "",
  score_max: "",
  date_from: "",
  date_to: "",
};

function toQuery(f: FilterState): ListFilters {
  const pick = (v: string) => (v === ALL || !v ? undefined : v);
  return {
    q: f.q.trim() || undefined,
    status: pick(f.status),
    portal: pick(f.portal),
    role_family: pick(f.role_family),
    channel: pick(f.channel),
    score_min: f.score_min ? Number(f.score_min) : undefined,
    score_max: f.score_max ? Number(f.score_max) : undefined,
    date_from: f.date_from ? (fromDateInput(f.date_from) ?? undefined) : undefined,
    date_to: f.date_to ? new Date(`${f.date_to}T23:59:59`).toISOString() : undefined,
  };
}

// The table/board choice is remembered per browser; the server always renders the table.
const viewListeners = new Set<() => void>();
function readView(): "table" | "board" {
  try {
    return localStorage.getItem(VIEW_KEY) === "board" ? "board" : "table";
  } catch {
    return "table";
  }
}
function writeView(view: "table" | "board") {
  try {
    localStorage.setItem(VIEW_KEY, view);
  } catch {
    /* private window: just don't remember */
  }
  viewListeners.forEach((l) => l());
}
function subscribeView(listener: () => void) {
  viewListeners.add(listener);
  return () => viewListeners.delete(listener);
}

function FilterSelect({
  value,
  onChange,
  placeholder,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
  options: { value: string; label: string }[];
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger size="sm" className="w-36">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{placeholder}</SelectItem>
        {options.map((o) => (
          <SelectItem key={o.value} value={o.value}>
            {o.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

export default function ApplicationsPage() {
  const [filters, setFilters] = useState<FilterState>(EMPTY);
  const view = useSyncExternalStore(subscribeView, readView, () => "table" as const);
  const query = toQuery(filters);
  const queryKey = JSON.stringify(query);
  const { data, error, loading, reload, setData } = useAsync(() => api.applications(query), [queryKey]);

  const set = (key: keyof FilterState) => (value: string) => setFilters((f) => ({ ...f, [key]: value }));
  const active = JSON.stringify(filters) !== JSON.stringify(EMPTY);

  const changeView = (v: string) => writeView(v === "board" ? "board" : "table");

  const move = async (id: number, status: Status) => {
    if (!data) return;
    const before = data;
    setData({ ...data, items: data.items.map((a) => (a.id === id ? { ...a, status } : a)) });
    try {
      await api.setStatus(id, status);
      toast.success(`Moved to ${STATUS_LABEL[status]}`);
      void reload();
    } catch (err) {
      setData(before);
      toast.error(err instanceof ApiError ? err.message : String(err));
    }
  };

  return (
    <div className="space-y-5">
      <PageHeader
        title="Applications"
        description={data ? `${data.total} job${data.total === 1 ? "" : "s"}${active ? " match the filters" : " tracked"}` : " "}
        actions={
          <>
            <Button asChild variant="outline" size="sm">
              <a href={api.exportCsvUrl(query)}>
                <Download className="size-4" /> Export CSV
              </a>
            </Button>
            <Button asChild size="sm">
              <Link href="/analyze">
                <Plus className="size-4" /> Analyze a job
              </Link>
            </Button>
          </>
        }
      />

      {data && (data.follow_ups_due > 0 || data.ghost_suggestions > 0) && (
        <div className="flex flex-wrap gap-2 text-sm">
          {data.follow_ups_due > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-amber-100 px-2.5 py-1 text-amber-900 dark:bg-amber-950 dark:text-amber-200">
              <BellRing className="size-4" /> {data.follow_ups_due} follow-up{data.follow_ups_due > 1 ? "s" : ""} due
            </span>
          )}
          {data.ghost_suggestions > 0 && (
            <span className="inline-flex items-center gap-1.5 rounded-md bg-muted px-2.5 py-1">
              <Ghost className="size-4" /> {data.ghost_suggestions} may be ghosted
            </span>
          )}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={filters.q}
          onChange={(e) => set("q")(e.target.value)}
          placeholder="Search company, title, notes"
          className="h-8 w-56"
        />
        <FilterSelect value={filters.status} onChange={set("status")} placeholder="All statuses" options={STATUSES.map((s) => ({ value: s, label: STATUS_LABEL[s] }))} />
        <FilterSelect value={filters.portal} onChange={set("portal")} placeholder="All portals" options={PORTALS.map((p) => ({ value: p, label: p }))} />
        <FilterSelect value={filters.role_family} onChange={set("role_family")} placeholder="All types" options={Object.entries(ROLE_FAMILY_LABEL).map(([value, label]) => ({ value, label }))} />
        <FilterSelect value={filters.channel} onChange={set("channel")} placeholder="All channels" options={CHANNELS.map((c) => ({ value: c, label: c[0].toUpperCase() + c.slice(1) }))} />
        <Input type="number" min={0} max={100} value={filters.score_min} onChange={(e) => set("score_min")(e.target.value)} placeholder="Min fit" className="h-8 w-24" aria-label="Minimum fit score" />
        <Input type="number" min={0} max={100} value={filters.score_max} onChange={(e) => set("score_max")(e.target.value)} placeholder="Max fit" className="h-8 w-24" aria-label="Maximum fit score" />
        <Input type="date" value={filters.date_from} onChange={(e) => set("date_from")(e.target.value)} className="h-8 w-36" aria-label="Added from" />
        <Input type="date" value={filters.date_to} onChange={(e) => set("date_to")(e.target.value)} className="h-8 w-36" aria-label="Added until" />
        {active && (
          <Button variant="ghost" size="sm" onClick={() => setFilters(EMPTY)}>
            <X className="size-4" /> Clear
          </Button>
        )}
        <Tabs value={view} onValueChange={changeView} className="ml-auto">
          <TabsList>
            <TabsTrigger value="table">
              <Rows3 className="size-4" /> Table
            </TabsTrigger>
            <TabsTrigger value="board">
              <LayoutGrid className="size-4" /> Board
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {loading && !data ? (
        <Skeleton className="h-80" />
      ) : error && !data ? (
        <ErrorState message={error.message} onRetry={reload} />
      ) : !data || data.items.length === 0 ? (
        active ? (
          <EmptyState title="No applications match these filters" action={<Button variant="outline" size="sm" onClick={() => setFilters(EMPTY)}>Clear filters</Button>} />
        ) : (
          <EmptyState
            title="No applications yet"
            action={
              <Button asChild size="sm">
                <Link href="/analyze">Analyze your first job</Link>
              </Button>
            }
          >
            Paste a job description and JobPilot will score it, tailor your resume and track it here.
          </EmptyState>
        )
      ) : view === "table" ? (
        <ApplicationsTable data={data.items} />
      ) : (
        <KanbanBoard data={data.items} onMove={move} />
      )}
    </div>
  );
}
