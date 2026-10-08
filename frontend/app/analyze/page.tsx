"use client";

import { ArrowRight, Loader2, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader, TaskProgress } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError, PORTALS, type TaskStatus } from "@/lib/api";
import { useTask } from "@/lib/hooks";

const MIN_CHARS = 20;

export default function AnalyzePage() {
  const router = useRouter();
  const [jd, setJd] = useState("");
  const [portal, setPortal] = useState("");
  const [url, setUrl] = useState("");
  const [force, setForce] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [result, setResult] = useState<TaskStatus | null>(null);

  const task = useTask(taskId, (t) => {
    setResult(t);
    if (t.state === "done" && t.application_id) {
      toast.success("Analysis finished");
      router.push(`/applications/${t.application_id}`);
    }
  });
  const running = !!taskId && (!task || task.state === "queued" || task.state === "running");

  const start = async () => {
    setStarting(true);
    setResult(null);
    try {
      const { task_id } = await api.analyze({
        jd_text: jd,
        source_portal: portal,
        url,
        tailor_despite_blockers: force,
      });
      setTaskId(task_id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : String(err));
    } finally {
      setStarting(false);
    }
  };

  const failedApp = result?.state === "error" ? result.application_id : null;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Analyze a job"
        description="Paste a job description (English or Arabic). JobPilot scores your fit, tailors your resume and drafts the messages. Nothing is sent anywhere."
      />
      <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
        <Card>
          <CardContent className="space-y-4 pt-6">
            <div className="space-y-2">
              <Label htmlFor="jd">Job description</Label>
              <Textarea
                id="jd"
                value={jd}
                onChange={(e) => setJd(e.target.value)}
                placeholder="Paste the full job description here…"
                className="min-h-80 font-mono text-sm"
                disabled={running}
                dir="auto"
              />
              <p className="text-xs text-muted-foreground">{jd.trim().length.toLocaleString()} characters</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Portal (optional)</Label>
                <Select value={portal} onValueChange={setPortal} disabled={running}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Where did you find it?" />
                  </SelectTrigger>
                  <SelectContent>
                    {PORTALS.map((p) => (
                      <SelectItem key={p} value={p}>
                        {p}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="url">Job URL (optional)</Label>
                <Input
                  id="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://…"
                  disabled={running}
                />
              </div>
            </div>
            <label className="flex items-start gap-2 text-sm">
              <Checkbox checked={force} onCheckedChange={(v) => setForce(v === true)} disabled={running} />
              <span>
                Tailor even if there&apos;s a hard blocker
                <span className="block text-muted-foreground">
                  Normally skipped to save free-tier API quota (e.g. &quot;Saudi nationals only&quot;).
                </span>
              </span>
            </label>
            <Button onClick={start} disabled={running || starting || jd.trim().length < MIN_CHARS}>
              {running || starting ? <Loader2 className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
              {running ? "Working…" : "Start"}
            </Button>
          </CardContent>
        </Card>

        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Progress</CardTitle>
            <CardDescription>
              {taskId ? "Usually 20–60 seconds; longer if the free tier is rate-limited." : "Starts when you click Start."}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <TaskProgress task={task} />
            {failedApp && (
              <Button asChild variant="outline" size="sm">
                <Link href={`/applications/${failedApp}`}>
                  The job was saved: open it <ArrowRight className="size-4" />
                </Link>
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
