"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getHealth, type HealthResponse } from "@/lib/api";

type Row = { label: string; ok: boolean; optional?: boolean; detail: string };

function rowsFrom(health: HealthResponse): Row[] {
  return [
    {
      label: `LLM (${health.llm.provider}, ${health.llm.model})`,
      ok: health.llm.configured,
      detail: health.llm.detail,
    },
    {
      label: "Truth bank",
      ok: health.truth_bank.found && health.truth_bank.valid,
      detail: [health.truth_bank.detail, ...health.truth_bank.problems.slice(0, 5)].join(" "),
    },
    {
      label: "Resume templates",
      ok: health.templates.missing.length === 0,
      detail: health.templates.detail,
    },
    {
      label: "LibreOffice (PDF export)",
      ok: health.libreoffice.found,
      optional: true,
      detail: health.libreoffice.path ?? health.libreoffice.detail,
    },
  ];
}

export function HealthPanel() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // State is only set after the request settles, so this is safe to call from an effect.
  const fetchHealth = useCallback(
    () =>
      getHealth()
        .then((data) => {
          setHealth(data);
          setError(null);
        })
        .catch((err: unknown) => {
          setHealth(null);
          setError(err instanceof Error ? err.message : String(err));
        })
        .finally(() => setLoading(false)),
    [],
  );

  useEffect(() => {
    void fetchHealth();
  }, [fetchHealth]);

  const recheck = () => {
    setLoading(true);
    void fetchHealth();
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1.5">
          <CardTitle>System health</CardTitle>
          <CardDescription>What the pipeline needs before it can run.</CardDescription>
        </div>
        <Button variant="outline" size="sm" onClick={recheck} disabled={loading}>
          {loading ? "Checking…" : "Recheck"}
        </Button>
      </CardHeader>
      <CardContent>
        {error && (
          <p className="text-sm text-destructive">
            Can&apos;t reach the backend ({error}). Is it running on port 8000?
          </p>
        )}
        {health && (
          <ul className="divide-y">
            {rowsFrom(health).map((row) => (
              <li key={row.label} className="flex items-start justify-between gap-4 py-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium">{row.label}</p>
                  <p className="text-sm wrap-break-word text-muted-foreground">{row.detail}</p>
                </div>
                <Badge variant={row.ok ? "default" : row.optional ? "secondary" : "destructive"}>
                  {row.ok ? "Ready" : row.optional ? "Optional" : "Missing"}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
