"use client";

import {
  ArrowLeft,
  BellRing,
  Copy as CopyIcon,
  Download,
  ExternalLink,
  Ghost,
  Loader2,
  RefreshCw,
  Save,
  Sparkles,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { LettersEditor, type Letters } from "@/components/application/letters-editor";
import { ResumeDiff } from "@/components/application/resume-diff";
import { ResumeEditor } from "@/components/application/resume-editor";
import { ScoreCard } from "@/components/application/score-card";
import { Timeline } from "@/components/application/timeline";
import { WarningsPanel } from "@/components/application/warnings-panel";
import { ErrorState, StatusBadge, TaskProgress } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  api,
  ApiError,
  CHANNELS,
  STATUSES,
  type ApplicationDetail,
  type ApplicationPatch,
  type ResumeContent,
  type Status,
} from "@/lib/api";
import { formatDate, fromDateInput, ROLE_FAMILY_LABEL, STATUS_LABEL, toDateInput } from "@/lib/format";
import { useAsync, useTask } from "@/lib/hooks";

const lettersOf = (d: ApplicationDetail): Letters => ({
  cover_letter: d.cover_letter,
  email_subject: d.email_subject,
  email_body: d.email_body,
  whatsapp_message: d.whatsapp_message,
});

const QUICK_STATUSES: { status: Status; label: string }[] = [
  { status: "applied", label: "Mark applied" },
  { status: "saved", label: "Save for later" },
  { status: "skipped", label: "Skip" },
];

function errorText(err: unknown): string {
  return err instanceof ApiError ? err.message : String(err);
}

export function ApplicationView({ id }: { id: number }) {
  const router = useRouter();
  const { data, error, loading, reload, setData } = useAsync(() => api.application(id), [id]);
  const [resumeDraft, setResumeDraft] = useState<ResumeContent | null>(null);
  const [lettersDraft, setLettersDraft] = useState<Letters | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [regenTask, setRegenTask] = useState<string | null>(null);

  const regen = useTask(regenTask, (t) => {
    setRegenTask(null);
    if (t.state === "done") {
      toast.success("Regenerated");
      setResumeDraft(null);
      setLettersDraft(null);
      void reload();
    } else toast.error(t.error ?? "Regeneration failed");
  });

  if (loading && !data) return <Skeleton className="h-[70vh]" />;
  if (!data) return <ErrorState message={error?.message ?? "Not found"} onRetry={reload} />;

  const resume = resumeDraft ?? data.resume;
  const letters = lettersDraft ?? lettersOf(data);
  const dirty = resumeDraft !== null || lettersDraft !== null;
  const jd = data.job.analysis.jd as Record<string, string>;

  const run = async (label: string, fn: () => Promise<ApplicationDetail | void>, success?: string) => {
    setBusy(label);
    try {
      const next = await fn();
      if (next) setData(next);
      if (success) toast.success(success);
    } catch (err) {
      toast.error(errorText(err));
    } finally {
      setBusy(null);
    }
  };

  const patch = (p: ApplicationPatch, success?: string) => run("patch", () => api.update(id, p), success);

  const saveEdits = async (rerender: boolean) => {
    const body: ApplicationPatch = {};
    if (resumeDraft) body.resume = resumeDraft;
    if (lettersDraft) Object.assign(body, lettersDraft);
    await run(
      rerender ? "rerender" : "save",
      async () => {
        let next = dirty ? await api.update(id, body) : data;
        if (rerender) next = await api.rerender(id);
        setResumeDraft(null);
        setLettersDraft(null);
        return next;
      },
      rerender ? "Saved and re-rendered" : "Saved",
    );
  };

  const setStatus = (status: Status) =>
    run("status", () => api.setStatus(id, status), `Status: ${STATUS_LABEL[status]}`);

  const regenerate = async (target: "resume" | "cover_letter") => {
    try {
      const { task_id } = await api.regenerate(id, target);
      setRegenTask(task_id);
    } catch (err) {
      toast.error(errorText(err));
    }
  };

  const remove = () =>
    run("delete", async () => {
      await api.remove(id);
      toast.success("Deleted");
      router.push("/applications");
    });

  const snooze = () => {
    const next = new Date(Date.now() + 7 * 86400_000).toISOString();
    void patch({ follow_up_at: next }, "Follow-up moved to next week");
  };

  const downloadDisabled = data.download_blocked || dirty;
  const downloadHint = dirty
    ? "Save & re-render first"
    : data.download_blocked
      ? "Confirm or fix the high-severity warnings first"
      : "";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-3">
        <Link href="/applications" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-4" /> Applications
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 space-y-1">
            <h1 className="text-2xl font-semibold tracking-tight wrap-break-word">{data.title}</h1>
            <p className="text-muted-foreground">
              {[data.company, data.city, data.source_portal].filter(Boolean).join(" · ")}
              {data.url && (
                <>
                  {" · "}
                  <a href={data.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 underline-offset-2 hover:underline">
                    posting <ExternalLink className="size-3" />
                  </a>
                </>
              )}
            </p>
            <div className="flex flex-wrap items-center gap-2 pt-1 text-sm">
              <StatusBadge status={data.status} />
              <span className="text-muted-foreground">
                {ROLE_FAMILY_LABEL[data.resume_variant] ?? data.resume_variant} resume · analysed {formatDate(data.created_at)}
                {data.applied_at && ` · applied ${formatDate(data.applied_at)}`}
              </span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {QUICK_STATUSES.filter((q) => q.status !== data.status).map((q) => (
              <Button key={q.status} variant={q.status === "applied" ? "default" : "outline"} size="sm" onClick={() => setStatus(q.status)} disabled={!!busy}>
                {q.label}
              </Button>
            ))}
            <Select value={data.status} onValueChange={(v) => setStatus(v as Status)}>
              <SelectTrigger size="sm" className="w-36" aria-label="Status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>
                    {STATUS_LABEL[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Banners */}
      {data.suggest_ghosted && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/50 p-3 text-sm">
          <span className="flex items-center gap-2">
            <Ghost className="size-4" /> No reply for 3 weeks since you applied. Mark it as ghosted?
          </span>
          <span className="flex gap-2">
            <Button size="sm" onClick={() => setStatus("ghosted")}>Mark ghosted</Button>
            <Button size="sm" variant="ghost" onClick={() => patch({ ghost_dismissed: true }, "Dismissed")}>
              Dismiss
            </Button>
          </span>
        </div>
      )}
      {data.follow_up_due && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          <span className="flex items-center gap-2">
            <BellRing className="size-4" /> Follow-up due (since {formatDate(data.follow_up_at)}).
          </span>
          <Button size="sm" variant="outline" onClick={snooze}>
            Followed up: remind me in a week
          </Button>
        </div>
      )}
      {data.duplicates.length > 0 && (
        <div className="space-y-1 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          <p className="font-medium">Possible duplicate of a job you already saved:</p>
          {data.duplicates.map((d) => (
            <p key={d.job_id}>
              <Link href={`/applications/${d.job_id}`} className="underline underline-offset-2">
                #{d.job_id} {d.company} · {d.title}
              </Link>{" "}
              ({STATUS_LABEL[d.status as Status] ?? d.status}
              {d.applied_at ? `, applied ${formatDate(d.applied_at)}` : ""}): {d.reasons.join(", ")}
            </p>
          ))}
        </div>
      )}

      {regenTask && (
        <Card>
          <CardContent className="pt-6">
            <TaskProgress task={regen} steps={["tailor"]} />
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        {/* Main column */}
        <div className="min-w-0 space-y-4">
          {!resume ? (
            <Card>
              <CardContent className="space-y-3 pt-6">
                <p className="font-medium">No tailored resume yet.</p>
                <p className="text-sm text-muted-foreground">{data.skip_reason || "Tailoring didn't run for this job."}</p>
                <Button onClick={() => regenerate("resume")} disabled={!!regenTask}>
                  <Sparkles className="size-4" /> Tailor anyway
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Tabs defaultValue="resume">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <TabsList>
                  <TabsTrigger value="resume">Resume</TabsTrigger>
                  <TabsTrigger value="diff">Diff vs base</TabsTrigger>
                  <TabsTrigger value="letters">Cover letter & messages</TabsTrigger>
                  <TabsTrigger value="jd">Job description</TabsTrigger>
                </TabsList>
                <div className="flex flex-wrap gap-2">
                  {dirty && (
                    <Button variant="ghost" size="sm" onClick={() => { setResumeDraft(null); setLettersDraft(null); }}>
                      Discard changes
                    </Button>
                  )}
                  <Button variant="outline" size="sm" onClick={() => saveEdits(false)} disabled={!dirty || !!busy}>
                    {busy === "save" ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />} Save
                  </Button>
                  <Button size="sm" onClick={() => saveEdits(true)} disabled={!!busy}>
                    {busy === "rerender" ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
                    {dirty ? "Save & re-render" : "Re-render"}
                  </Button>
                </div>
              </div>
              <TabsContent value="resume" className="pt-4">
                <ResumeEditor value={resume} onChange={setResumeDraft} />
              </TabsContent>
              <TabsContent value="diff" className="pt-4">
                <ResumeDiff resume={resume} />
              </TabsContent>
              <TabsContent value="letters" className="pt-4">
                <LettersEditor value={letters} onChange={setLettersDraft} />
              </TabsContent>
              <TabsContent value="jd" className="pt-4">
                <JobDescription data={data} jd={jd} />
              </TabsContent>
            </Tabs>
          )}
          {!resume && <JobDescription data={data} jd={jd} />}
        </div>

        {/* Side column */}
        <div className="space-y-4">
          {resume && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Files</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <Button asChild={!downloadDisabled && data.has_docx} disabled={downloadDisabled || !data.has_docx} title={downloadHint}>
                    <a href={api.downloadUrl(id, "docx")}>
                      <Download className="size-4" /> DOCX
                    </a>
                  </Button>
                  <Button asChild={!downloadDisabled && data.has_pdf} disabled={downloadDisabled || !data.has_pdf} variant="outline" title={downloadHint || data.pdf_note}>
                    <a href={api.downloadUrl(id, "pdf")}>
                      <Download className="size-4" /> PDF
                    </a>
                  </Button>
                </div>
                {downloadHint && <p className="text-xs text-muted-foreground">{downloadHint}.</p>}
                {!data.has_pdf && data.pdf_note && <p className="text-xs text-muted-foreground">{data.pdf_note}</p>}
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={async () => {
                    try {
                      await navigator.clipboard.writeText(letters.cover_letter);
                      toast.success("Cover letter copied");
                    } catch {
                      toast.error("Couldn't copy");
                    }
                  }}
                >
                  <CopyIcon className="size-4" /> Copy cover letter
                </Button>
                <div className="flex gap-2">
                  <Button variant="ghost" size="sm" className="flex-1" onClick={() => regenerate("resume")} disabled={!!regenTask}>
                    <Sparkles className="size-4" /> New resume
                  </Button>
                  <Button variant="ghost" size="sm" className="flex-1" onClick={() => regenerate("cover_letter")} disabled={!!regenTask}>
                    <Sparkles className="size-4" /> New letters
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">Regenerating uses one LLM call and replaces your edits.</p>
              </CardContent>
            </Card>
          )}

          {resume && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle>Validator</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <WarningsPanel
                  warnings={data.warnings}
                  confirmed={data.warnings_confirmed}
                  busy={!!busy}
                  onConfirm={() => patch({ warnings_confirmed: true }, "Confirmed")}
                />
                {dirty && <p className="text-xs text-muted-foreground">Unsaved edits are checked when you save.</p>}
                {data.tailor_issues.length > 0 && (
                  <details className="text-xs text-muted-foreground">
                    <summary className="cursor-pointer">Tailoring notes ({data.tailor_issues.length})</summary>
                    <ul className="mt-1 list-disc space-y-0.5 pl-4">
                      {data.tailor_issues.map((i) => (
                        <li key={i}>{i}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </CardContent>
            </Card>
          )}

          <ScoreCard fit={data.fit} />

          <DetailsCard data={data} onPatch={patch} busy={!!busy} />

          <Card>
            <CardHeader className="pb-3">
              <CardTitle>Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              <Timeline events={data.events} />
            </CardContent>
          </Card>

          <Dialog>
            <DialogTrigger asChild>
              <Button variant="ghost" size="sm" className="w-full text-muted-foreground hover:text-destructive">
                <Trash2 className="size-4" /> Delete application
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Delete this application?</DialogTitle>
                <DialogDescription>
                  This removes the application, its timeline and its generated files. It can&apos;t be undone.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline">Cancel</Button>
                </DialogClose>
                <Button variant="destructive" onClick={remove} disabled={!!busy}>
                  Delete
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>
    </div>
  );
}

function JobDescription({ data, jd }: { data: ApplicationDetail; jd: Record<string, string> }) {
  const facts = [
    ["Employment", data.job.employment_type],
    ["Salary", data.job.salary_text],
    ["Deadline", data.job.deadline],
    ["How to apply", jd.how_to_apply],
    ["Contact", [jd.contact_email, jd.contact_phone, jd.contact_whatsapp].filter(Boolean).join(", ")],
  ].filter(([, v]) => v);
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle>Job description</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {facts.length > 0 && (
          <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[140px_1fr]">
            {facts.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="wrap-break-word">{v}</dd>
              </div>
            ))}
          </dl>
        )}
        <pre dir="auto" className="max-h-[60vh] overflow-auto rounded-md bg-muted/50 p-3 font-sans text-sm whitespace-pre-wrap">
          {data.job.jd_text}
        </pre>
      </CardContent>
    </Card>
  );
}

function DetailsCard({
  data,
  onPatch,
  busy,
}: {
  data: ApplicationDetail;
  onPatch: (p: ApplicationPatch, success?: string) => Promise<void>;
  busy: boolean;
}) {
  const [notes, setNotes] = useState(data.notes);
  const [contactName, setContactName] = useState(data.contact_name);
  const [contactInfo, setContactInfo] = useState(data.contact_info);
  const changed = notes !== data.notes || contactName !== data.contact_name || contactInfo !== data.contact_info;
  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle>Details</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-xs">Channel</Label>
            <Select value={data.channel} onValueChange={(v) => onPatch({ channel: v as ApplicationDetail["channel"] })}>
              <SelectTrigger size="sm" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CHANNELS.map((c) => (
                  <SelectItem key={c} value={c} className="capitalize">
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Follow up on</Label>
            <Input
              type="date"
              className="h-8"
              value={toDateInput(data.follow_up_at)}
              onChange={(e) => onPatch({ follow_up_at: fromDateInput(e.target.value) }, "Follow-up date saved")}
            />
          </div>
          <div className="col-span-2 space-y-1">
            <Label className="text-xs">Applied on</Label>
            <Input
              type="date"
              className="h-8"
              value={toDateInput(data.applied_at)}
              onChange={(e) => onPatch({ applied_at: fromDateInput(e.target.value) }, "Applied date saved")}
            />
          </div>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Contact name</Label>
          <Input value={contactName} onChange={(e) => setContactName(e.target.value)} className="h-8" />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Contact info</Label>
          <Input value={contactInfo} onChange={(e) => setContactInfo(e.target.value)} className="h-8" placeholder="email, phone, WhatsApp" />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Notes</Label>
          <Textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3} />
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={!changed || busy}
          onClick={() => onPatch({ notes, contact_name: contactName, contact_info: contactInfo }, "Details saved")}
        >
          Save details
        </Button>
      </CardContent>
    </Card>
  );
}
