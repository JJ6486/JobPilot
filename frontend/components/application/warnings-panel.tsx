"use client";

import { AlertTriangle, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { ValidationWarning } from "@/lib/api";

export function WarningsPanel({
  warnings,
  confirmed,
  onConfirm,
  busy,
}: {
  warnings: ValidationWarning[];
  confirmed: boolean;
  onConfirm: () => void;
  busy: boolean;
}) {
  const high = warnings.filter((w) => w.severity === "high");
  const medium = warnings.filter((w) => w.severity === "medium");
  if (!warnings.length) {
    return (
      <p className="flex items-center gap-2 text-sm text-emerald-700 dark:text-emerald-400">
        <ShieldCheck className="size-4" /> No validator warnings: everything traces back to your truth bank.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {high.length > 0 && (
        <div className="space-y-2 rounded-md border border-destructive/50 bg-destructive/10 p-3">
          <p className="flex items-center gap-2 text-sm font-semibold text-destructive">
            <AlertTriangle className="size-4" />
            {high.length} high-severity warning{high.length > 1 ? "s" : ""}: possible claims not in your truth bank
          </p>
          <ul className="space-y-1.5 text-sm">
            {high.map((w, i) => (
              <li key={`${w.location}-${w.text}-${i}`}>
                <span className="font-medium">&ldquo;{w.text}&rdquo;</span>{" "}
                <span className="text-muted-foreground">
                  in {w.location}: {w.message}
                </span>
              </li>
            ))}
          </ul>
          {confirmed ? (
            <p className="text-sm text-muted-foreground">You confirmed this text is true. Downloads are unlocked.</p>
          ) : (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <Button size="sm" variant="destructive" onClick={onConfirm} disabled={busy}>
                I confirm this is true
              </Button>
              <span className="text-xs text-muted-foreground">or fix the text, save, and re-render.</span>
            </div>
          )}
        </div>
      )}
      {medium.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-sm font-medium">
            {medium.length} to double-check
          </p>
          <ul className="space-y-1 text-sm text-muted-foreground">
            {medium.map((w, i) => (
              <li key={`${w.location}-${w.text}-${i}`}>
                <span className="text-foreground">&ldquo;{w.text}&rdquo;</span> in {w.location}: {w.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
