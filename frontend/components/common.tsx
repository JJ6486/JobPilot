"use client";

import { AlertTriangle, Check, CheckCircle2, Circle, Copy, Inbox, Loader2, MinusCircle, XCircle } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Status, TaskStatus } from "@/lib/api";
import { STATUS_LABEL } from "@/lib/format";
import { cn } from "@/lib/utils";

// Status colours: progress statuses lean primary, negative ones muted/destructive.
const STATUS_CLASS: Record<Status, string> = {
  saved: "bg-muted text-muted-foreground",
  tailored: "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200",
  applied: "bg-blue-100 text-blue-900 dark:bg-blue-950 dark:text-blue-200",
  replied: "bg-violet-100 text-violet-900 dark:bg-violet-950 dark:text-violet-200",
  interview: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  offer: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  rejected: "bg-rose-100 text-rose-900 dark:bg-rose-950 dark:text-rose-200",
  ghosted: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  skipped: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  withdrawn: "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
};

export function StatusBadge({ status }: { status: Status }) {
  return (
    <Badge variant="outline" className={cn("border-transparent font-medium", STATUS_CLASS[status])}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}

const REC_CLASS: Record<string, string> = {
  apply: "bg-emerald-600 text-white dark:bg-emerald-500 dark:text-emerald-950",
  maybe: "bg-amber-500 text-amber-950",
  skip: "bg-rose-600 text-white dark:bg-rose-500 dark:text-rose-950",
};

export function ScoreBadge({ score, recommendation }: { score: number; recommendation: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="font-semibold tabular-nums">{score}</span>
      {recommendation && (
        <span className={cn("rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase", REC_CLASS[recommendation])}>
          {recommendation}
        </span>
      )}
    </span>
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Couldn't copy. Select the text and copy manually.");
    }
  };
  return (
    <Button variant="outline" size="sm" onClick={copy} disabled={!text}>
      {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
      {copied ? "Copied" : label}
    </Button>
  );
}

const STEP_LABEL: Record<string, string> = {
  parse: "Read the job description",
  dedupe: "Check for duplicates",
  score: "Score fit",
  tailor: "Tailor resume",
  letter: "Write cover letter & messages",
  save: "Save to tracker",
};

export function TaskProgress({ task, steps }: { task: TaskStatus | null; steps?: string[] }) {
  const order = steps ?? Object.keys(STEP_LABEL);
  const byName = new Map(task?.steps.map((s) => [s.step, s]) ?? []);
  const lastMessage = task?.messages.at(-1);
  const waiting = task?.state === "running" && lastMessage && /retrying/i.test(lastMessage);
  return (
    <div className="space-y-3">
      <ol className="space-y-2">
        {order.map((name) => {
          const s = byName.get(name);
          const state = s?.state ?? (task?.state === "error" ? "error" : "pending");
          return (
            <li key={name} className="flex items-start gap-3 text-sm">
              <span className="mt-0.5">
                {state === "done" ? (
                  <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" />
                ) : state === "running" ? (
                  <Loader2 className="size-4 animate-spin text-primary" />
                ) : state === "skipped" ? (
                  <MinusCircle className="size-4 text-muted-foreground" />
                ) : state === "error" ? (
                  <XCircle className="size-4 text-muted-foreground/50" />
                ) : (
                  <Circle className="size-4 text-muted-foreground/40" />
                )}
              </span>
              <span className="min-w-0">
                <span className={cn(state === "pending" && "text-muted-foreground")}>{STEP_LABEL[name] ?? name}</span>
                {s?.detail && <span className="block wrap-break-word text-muted-foreground">{s.detail}</span>}
              </span>
            </li>
          );
        })}
      </ol>
      {waiting && (
        <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          <Loader2 className="mt-0.5 size-4 shrink-0 animate-spin" />
          <span>
            <strong>Rate-limited, retrying.</strong> {lastMessage}
          </span>
        </div>
      )}
      {task?.state === "error" && (
        <div className="flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <span className="wrap-break-word">{task.error}</span>
        </div>
      )}
    </div>
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-10 text-center">
      <Inbox className="size-8 text-muted-foreground" />
      <div className="space-y-1">
        <p className="font-medium">{title}</p>
        {children && <p className="text-sm text-muted-foreground">{children}</p>}
      </div>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm">
      <p className="flex items-center gap-2 font-medium text-destructive">
        <AlertTriangle className="size-4" /> Something went wrong
      </p>
      <p className="wrap-break-word text-muted-foreground">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
