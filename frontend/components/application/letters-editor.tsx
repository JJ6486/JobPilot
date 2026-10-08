"use client";

import { CopyButton } from "@/components/common";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { wordCount } from "@/lib/format";
import { cn } from "@/lib/utils";

export type Letters = {
  cover_letter: string;
  email_subject: string;
  email_body: string;
  whatsapp_message: string;
};

function Count({ text, min = 0, max }: { text: string; min?: number; max: number }) {
  const n = wordCount(text);
  const ok = n >= min && n <= max;
  return (
    <span className={cn("text-xs tabular-nums", ok ? "text-muted-foreground" : "text-amber-700 dark:text-amber-400")}>
      {n} words {min ? `(${min}–${max})` : `(max ${max})`}
    </span>
  );
}

export function LettersEditor({ value, onChange }: { value: Letters; onChange: (next: Letters) => void }) {
  const set = (key: keyof Letters, v: string) => onChange({ ...value, [key]: v });
  const email = `Subject: ${value.email_subject}\n\n${value.email_body}`;
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Label htmlFor="cover">Cover letter</Label>
          <div className="flex items-center gap-3">
            <Count text={value.cover_letter} min={100} max={200} />
            <CopyButton text={value.cover_letter} label="Copy cover letter" />
          </div>
        </div>
        <Textarea id="cover" value={value.cover_letter} onChange={(e) => set("cover_letter", e.target.value)} rows={14} />
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Label htmlFor="subject">Email</Label>
          <div className="flex items-center gap-3">
            <Count text={value.email_body} max={100} />
            <CopyButton text={email} label="Copy email" />
          </div>
        </div>
        <Input id="subject" value={value.email_subject} onChange={(e) => set("email_subject", e.target.value)} placeholder="Subject" />
        <Textarea value={value.email_body} onChange={(e) => set("email_body", e.target.value)} rows={7} aria-label="Email body" />
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Label htmlFor="wa">WhatsApp message</Label>
          <div className="flex items-center gap-3">
            <Count text={value.whatsapp_message} max={60} />
            <CopyButton text={value.whatsapp_message} label="Copy message" />
          </div>
        </div>
        <Textarea id="wa" value={value.whatsapp_message} onChange={(e) => set("whatsapp_message", e.target.value)} rows={4} />
      </div>
    </div>
  );
}
