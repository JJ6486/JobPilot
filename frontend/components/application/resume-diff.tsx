"use client";

import { diffArrays } from "diff";
import { useMemo } from "react";

import { ErrorState } from "@/components/common";
import { Skeleton } from "@/components/ui/skeleton";
import { api, type ResumeContent } from "@/lib/api";
import { resumeToLines } from "@/lib/format";
import { useAsync } from "@/lib/hooks";
import { cn } from "@/lib/utils";

// Sections filled in from the truth bank on every resume, so they're never "tailored".
const FIXED_SECTIONS = new Set(["EDUCATION", "LANGUAGES", "OTHER INFORMATION"]);
const isHeading = (line: string) => /^[A-Z&\s]{4,}$/.test(line) && line === line.toUpperCase();

/** The base resume's lines minus the name/contact header and the fixed sections. */
function tailorableLines(lines: string[]): string[] {
  const summaryAt = lines.indexOf("SUMMARY");
  const out: string[] = summaryAt > 1 ? [lines[1]] : []; // keep the headline, drop name + contact
  let section = "";
  for (const line of lines.slice(Math.max(summaryAt, 0))) {
    if (isHeading(line)) section = line;
    if (!FIXED_SECTIONS.has(section)) out.push(line);
  }
  return out;
}

/** Line diff of the tailored resume against the original base resume. */
export function ResumeDiff({ resume }: { resume: ResumeContent }) {
  const base = useAsync(() => api.baseResumeText(resume.role_family), [resume.role_family]);

  const parts = useMemo(
    () => (base.data ? diffArrays(tailorableLines(base.data.lines), resumeToLines(resume)) : []),
    [base.data, resume],
  );

  if (base.loading) return <Skeleton className="h-96" />;
  if (base.error) return <ErrorState message={base.error.message} onRetry={base.reload} />;

  const added = parts.filter((p) => p.added).reduce((n, p) => n + p.value.length, 0);
  const removed = parts.filter((p) => p.removed).reduce((n, p) => n + p.value.length, 0);

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">
        Compared with <span className="font-medium text-foreground">{base.data?.file}</span>:{" "}
        <span className="text-emerald-700 dark:text-emerald-400">{added} lines added or reworded</span>,{" "}
        <span className="text-rose-700 dark:text-rose-400">{removed} lines removed</span>. Contact details,
        education, languages and other fixed sections are filled in from your truth bank and aren&apos;t shown.
      </p>
      <div className="max-h-[70vh] overflow-auto rounded-lg border font-mono text-xs leading-relaxed">
        {parts.map((part, i) =>
          part.value.map((line, j) => (
            <div
              key={`${i}-${j}`}
              className={cn(
                "flex gap-2 border-l-2 px-3 py-0.5 whitespace-pre-wrap",
                part.added && "border-emerald-500 bg-emerald-50 dark:bg-emerald-950/40",
                part.removed && "border-rose-500 bg-rose-50 text-muted-foreground line-through dark:bg-rose-950/40",
                !part.added && !part.removed && "border-transparent",
              )}
            >
              <span className="w-3 shrink-0 select-none text-muted-foreground">
                {part.added ? "+" : part.removed ? "−" : ""}
              </span>
              <span className="min-w-0">{line}</span>
            </div>
          )),
        )}
      </div>
    </div>
  );
}
