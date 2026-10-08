"use client";

import Link from "next/link";

import { CountBars, Funnel, RateBars, StatTile, WeeklyChart } from "@/components/analytics/charts";
import { EmptyState, ErrorState, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { ROLE_FAMILY_LABEL } from "@/lib/format";
import { useAsync } from "@/lib/hooks";

const PORTAL_LABEL: Record<string, string> = { "": "(not set)" };

export default function AnalyticsPage() {
  const summary = useAsync(() => api.summary(), []);
  const gaps = useAsync(() => api.skillGaps(), []);

  if ((summary.loading && !summary.data) || (gaps.loading && !gaps.data))
    return <Skeleton className="h-[70vh]" />;
  if (!summary.data || !gaps.data)
    return (
      <ErrorState
        message={(summary.error ?? gaps.error)?.message ?? "Couldn't load analytics"}
        onRetry={() => {
          void summary.reload();
          void gaps.reload();
        }}
      />
    );

  const s = summary.data;
  const g = gaps.data;
  if (s.total === 0)
    return (
      <div className="space-y-6">
        <PageHeader title="Analytics" />
        <EmptyState
          title="No data yet"
          action={
            <Button asChild size="sm">
              <Link href="/analyze">Analyze a job</Link>
            </Button>
          }
        >
          Charts appear once you&apos;ve analysed and applied to a few jobs.
        </EmptyState>
      </div>
    );

  const applied = s.funnel.applied;
  const responseRate = applied ? Math.round((s.funnel.replied / applied) * 100) : null;

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics" description="Computed from your tracker. No LLM calls." />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatTile label="Jobs analysed" value={s.total} />
        <StatTile label="Applications sent" value={applied} />
        <StatTile
          label="Response rate"
          value={responseRate === null ? "–" : `${responseRate}%`}
          hint={applied ? `${s.funnel.replied} of ${applied} got a reply` : "Mark jobs as applied to track this"}
        />
        <StatTile
          label="Median days to first reply"
          value={s.median_days_to_first_reply ?? "–"}
          hint={s.median_days_to_first_reply === null ? "No replies recorded yet" : undefined}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Per week</CardTitle>
            <CardDescription>Jobs analysed and applications sent, last 12 weeks</CardDescription>
          </CardHeader>
          <CardContent>
            <WeeklyChart data={s.per_week} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Funnel</CardTitle>
            <CardDescription>How far applications got (share of applied)</CardDescription>
          </CardHeader>
          <CardContent>
            <Funnel funnel={s.funnel} />
          </CardContent>
        </Card>
      </div>

      <div>
        <h2 className="mb-1 text-lg font-semibold">Response rate</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Share of sent applications that got any reply (reply, interview, offer or rejection).
        </p>
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">By fit score</CardTitle>
              <CardDescription>Does the score predict replies?</CardDescription>
            </CardHeader>
            <CardContent>
              <RateBars rows={s.response_by_score_band} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">By portal</CardTitle>
            </CardHeader>
            <CardContent>
              <RateBars rows={s.response_by_portal} labels={PORTAL_LABEL} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">By role type</CardTitle>
            </CardHeader>
            <CardContent>
              <RateBars rows={s.response_by_role_family} labels={ROLE_FAMILY_LABEL} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">By resume variant</CardTitle>
            </CardHeader>
            <CardContent>
              <RateBars rows={s.response_by_resume_variant} labels={ROLE_FAMILY_LABEL} />
            </CardContent>
          </Card>
        </div>
      </div>

      <div>
        <h2 className="mb-1 text-lg font-semibold">Skills gap report</h2>
        <p className="mb-3 text-sm text-muted-foreground">
          Across {g.jobs_analysed} analysed job{g.jobs_analysed === 1 ? "" : "s"}: what to learn next.
        </p>
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Most-requested missing skills</CardTitle>
            </CardHeader>
            <CardContent>
              <CountBars rows={g.missing} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Adjacent skills (partly covered)</CardTitle>
            </CardHeader>
            <CardContent>
              <CountBars rows={g.adjacent} />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
