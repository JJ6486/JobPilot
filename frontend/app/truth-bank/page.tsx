"use client";

import { CheckCircle2, Loader2, Save, ShieldCheck, Undo2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { ErrorState, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import { useAsync } from "@/lib/hooks";

export default function TruthBankPage() {
  const { data, error, loading, reload, setData } = useAsync(() => api.truthBank(), []);
  const [draft, setDraft] = useState<string | null>(null);
  const [problems, setProblems] = useState<string[] | null>(null);
  const [busy, setBusy] = useState<"validate" | "save" | null>(null);

  if (loading && !data) return <Skeleton className="h-[70vh]" />;
  if (!data) return <ErrorState message={error?.message ?? "Couldn't load the truth bank"} onRetry={reload} />;

  const text = draft ?? data.yaml;
  const dirty = draft !== null && draft !== data.yaml;
  const shown = problems ?? (dirty ? null : data.problems);

  const validate = async () => {
    setBusy("validate");
    try {
      const res = await api.validateTruthBank(text);
      setProblems(res.problems);
      if (res.valid) toast.success("Looks good: the truth bank is valid");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    setBusy("save");
    try {
      const res = await api.saveTruthBank(text);
      setData(res);
      setDraft(null);
      setProblems([]);
      toast.success("Saved. The previous version was backed up to data/backups/");
    } catch (err) {
      if (err instanceof ApiError && err.problems.length) {
        setProblems(err.problems);
        toast.error("Not saved: fix the problems listed below");
      } else toast.error(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Truth bank"
        description="Everything JobPilot may say about you. Tailoring can only select and rephrase what's here; anything else shows up as a gap."
        actions={
          <>
            {dirty && (
              <Button variant="ghost" size="sm" onClick={() => { setDraft(null); setProblems(null); }}>
                <Undo2 className="size-4" /> Discard
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={validate} disabled={!!busy}>
              {busy === "validate" ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />} Validate
            </Button>
            <Button size="sm" onClick={save} disabled={!dirty || !!busy}>
              {busy === "save" ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />} Save
            </Button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <Textarea
          value={text}
          onChange={(e) => {
            setDraft(e.target.value);
            setProblems(null);
          }}
          spellCheck={false}
          className="min-h-[70vh] font-mono text-xs leading-relaxed"
          aria-label="Truth bank YAML"
        />
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Validation</CardTitle>
              <CardDescription>Saving is refused while there are problems.</CardDescription>
            </CardHeader>
            <CardContent>
              {shown === null ? (
                <p className="text-sm text-muted-foreground">Unsaved changes. Click Validate to check them.</p>
              ) : shown.length === 0 ? (
                <p className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400">
                  <CheckCircle2 className="size-4" /> Valid
                </p>
              ) : (
                <ul className="space-y-1.5 text-sm">
                  {shown.map((p) => (
                    <li key={p} className="wrap-break-word text-destructive">
                      {p}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Reminders</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                <code>profile</code> and any <code>*_local_only</code> field never reach the LLM; they&apos;re
                added only when the resume file is rendered.
              </p>
              <p>
                Skill <code>level</code>: <code>core</code> = used at work, <code>project</code> = personal or
                academic, <code>learning</code> = shown only as &quot;Currently learning&quot;.
              </p>
              <p>Keep ids stable: past applications refer to them.</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
