"use client";

import { BellRing, Ghost, Plus } from "lucide-react";
import Link from "next/link";

import { StatTile } from "@/components/analytics/charts";
import { EmptyState, ErrorState, PageHeader, ScoreBadge, StatusBadge } from "@/components/common";
import { HealthPanel } from "@/components/health-panel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type ApplicationSummary } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { useAsync } from "@/lib/hooks";

const WEEK_MS = 7 * 86400_000;

function AppRow({ app, extra }: { app: ApplicationSummary; extra?: string }) {
  return (
    <li>
      <Link
        href={`/applications/${app.id}`}
        className="-mx-2 flex items-center justify-between gap-3 rounded-md px-2 py-2 hover:bg-muted/60"
      >
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium">{app.title}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {[app.company, extra].filter(Boolean).join(" · ")}
          </span>
        </span>
        <span className="flex shrink-0 items-center gap-2">
          <ScoreBadge score={app.fit_score} recommendation={app.recommendation} />
          <StatusBadge status={app.status} />
        </span>
      </Link>
    </li>
  );
}

export default function Dashboard() {
  // Stamp the load time with the data so "this week" doesn't call Date.now() during render.
  const { data, error, loading, reload } = useAsync(
    () => api.applications().then((list) => ({ ...list, loadedAt: Date.now() })),
    [],
  );

  if (loading && !data) return <Skeleton className="h-[60vh]" />;

  const items = data?.items ?? [];
  const followUps = items.filter((a) => a.follow_up_due);
  const ghosts = items.filter((a) => a.suggest_ghosted);
  const loadedAt = data?.loadedAt ?? 0;
  const appliedThisWeek = items.filter(
    (a) => a.applied_at && loadedAt - new Date(a.applied_at).getTime() < WEEK_MS,
  ).length;
  const waiting = items.filter((a) => a.status === "applied").length;
  const toApply = items.filter((a) => a.status === "tailored").length;
  const recent = items.slice(0, 6);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description="What needs your attention today."
        actions={
          <Button asChild size="sm">
            <Link href="/analyze">
              <Plus className="size-4" /> Analyze a job
            </Link>
          </Button>
        }
      />

      {error && !data && <ErrorState message={error.message} onRetry={reload} />}

      {data && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatTile label="Follow-ups due" value={data.follow_ups_due} hint={data.follow_ups_due ? "See the list below" : "You're up to date"} />
          <StatTile label="Applied this week" value={appliedThisWeek} />
          <StatTile label="Waiting for a reply" value={waiting} />
          <StatTile label="Tailored, not yet applied" value={toApply} />
        </div>
      )}

      {data && items.length === 0 && (
        <EmptyState
          title="Nothing tracked yet"
          action={
            <Button asChild size="sm">
              <Link href="/analyze">Analyze your first job</Link>
            </Button>
          }
        >
          Paste a job description to get a fit score, a tailored resume and a cover letter.
        </EmptyState>
      )}

      {items.length > 0 && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="flex items-center gap-2 text-base">
                <BellRing className="size-4" /> Follow-ups due
              </CardTitle>
            </CardHeader>
            <CardContent>
              {followUps.length ? (
                <ul>
                  {followUps.map((a) => (
                    <AppRow key={a.id} app={a} extra={`due ${formatDate(a.follow_up_at)}`} />
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">No follow-ups due.</p>
              )}
              {ghosts.length > 0 && (
                <div className="mt-4 border-t pt-3">
                  <p className="mb-1 flex items-center gap-2 text-sm font-medium">
                    <Ghost className="size-4" /> No reply in 3+ weeks: mark as ghosted?
                  </p>
                  <ul>
                    {ghosts.map((a) => (
                      <AppRow key={a.id} app={a} extra={`applied ${formatDate(a.applied_at)}`} />
                    ))}
                  </ul>
                </div>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-base">Recent</CardTitle>
              <Link href="/applications" className="text-sm text-muted-foreground hover:text-foreground">
                View all
              </Link>
            </CardHeader>
            <CardContent>
              <ul>
                {recent.map((a) => (
                  <AppRow key={a.id} app={a} extra={formatDate(a.created_at)} />
                ))}
              </ul>
            </CardContent>
          </Card>
        </div>
      )}

      <HealthPanel />
    </div>
  );
}
