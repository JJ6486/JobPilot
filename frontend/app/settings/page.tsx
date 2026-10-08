import { PageHeader } from "@/components/common";
import { HealthPanel } from "@/components/health-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Configuration lives in the .env file at the project root. Restart `npm run dev` after editing it."
      />
      <HealthPanel />
      <Card>
        <CardHeader>
          <CardTitle>Configuration (.env)</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-[220px_1fr]">
            <dt className="font-mono text-xs">LLM_PROVIDER</dt>
            <dd className="text-muted-foreground">gemini (default) or openai_compat (Groq, OpenRouter, Ollama)</dd>
            <dt className="font-mono text-xs">LLM_MODEL</dt>
            <dd className="text-muted-foreground">Empty = gemini-flash-latest</dd>
            <dt className="font-mono text-xs">LLM_FALLBACK_MODELS</dt>
            <dd className="text-muted-foreground">Tried in order when the main model is busy or out of free quota</dd>
            <dt className="font-mono text-xs">GEMINI_API_KEY</dt>
            <dd className="text-muted-foreground">Free key from aistudio.google.com/apikey</dd>
            <dt className="font-mono text-xs">LIBREOFFICE_PATH</dt>
            <dd className="text-muted-foreground">Only if LibreOffice isn&apos;t in the default install location</dd>
          </dl>
          <p className="text-muted-foreground">
            Free LLM tiers may use prompts to improve their models. Your name, phone, email, links and
            certificate URLs are never sent: they&apos;re added locally when the resume file is rendered.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
