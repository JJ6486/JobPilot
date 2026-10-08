// Typed client for the FastAPI backend. Requests go to /api/* and are proxied by next.config.ts.

export const STATUSES = [
  "saved",
  "tailored",
  "applied",
  "replied",
  "interview",
  "offer",
  "rejected",
  "ghosted",
  "skipped",
  "withdrawn",
] as const;
export type Status = (typeof STATUSES)[number];

export const CHANNELS = ["portal", "email", "whatsapp", "other"] as const;
export type Channel = (typeof CHANNELS)[number];

export const PORTALS = ["Indeed", "Bayt", "Naukrigulf", "LinkedIn", "Email", "WhatsApp", "Other"];

export type HealthResponse = {
  status: string;
  llm: { configured: boolean; provider: string; model: string; detail: string };
  libreoffice: { found: boolean; path: string | null; detail: string };
  truth_bank: { found: boolean; valid: boolean; detail: string; problems: string[] };
  templates: { files: string[]; missing: string[]; detail: string };
};

export type TaskStep = { step: string; state: string; detail: string };
export type TaskStatus = {
  id: string;
  kind: string;
  state: "queued" | "running" | "done" | "error";
  steps: TaskStep[];
  messages: string[];
  application_id: number | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
};

export type ApplicationSummary = {
  id: number;
  job_id: number;
  status: Status;
  fit_score: number;
  recommendation: "apply" | "maybe" | "skip" | "";
  title: string;
  company: string;
  city: string;
  source_portal: string;
  url: string;
  role_family: string;
  channel: Channel;
  applied_at: string | null;
  follow_up_at: string | null;
  follow_up_due: boolean;
  suggest_ghosted: boolean;
  created_at: string;
  updated_at: string;
};

export type ApplicationList = {
  items: ApplicationSummary[];
  total: number;
  page: number;
  page_size: number;
  follow_ups_due: number;
  ghost_suggestions: number;
};

export type ResumeBullet = { source_id: string; text: string };
export type ResumeEntry = {
  source_id: string;
  heading: string;
  title: string;
  dates: string;
  bullets: ResumeBullet[];
};
export type ResumeContent = {
  role_family: "software_ict" | "teaching";
  headline: string;
  summary: string;
  experience: ResumeEntry[];
  teaching_intro: ResumeBullet[];
  teaching_roles: ResumeEntry[];
  workshops: ResumeBullet[];
  projects: ResumeEntry[];
  skill_groups: { label: string; skills: string[] }[];
  currently_learning: string[];
  achievements: { source_id: string; title: string; meta: string; text: string }[];
  certifications: { source_id: string; name: string; rest: string }[];
  leadership: ResumeBullet[];
};

export type Requirement = {
  requirement: string;
  kind: "must" | "nice";
  result: "matched" | "adjacent" | "missing";
  evidence_ids: string[];
  matched_skill: string;
  note: string;
};

export type FitScore = {
  score: number;
  recommendation: "apply" | "maybe" | "skip";
  breakdown: { must: number; experience: number; role: number; nice: number; logistics: number };
  blockers: string[];
  matched: string[];
  adjacent: string[];
  missing: string[];
  red_flags: string[];
  summary: string[];
  requirements: Requirement[];
};

export type ValidationWarning = {
  severity: "high" | "medium";
  location: string;
  text: string;
  message: string;
};

export type Duplicate = {
  job_id: string;
  company: string;
  title: string;
  reasons: string[];
  similarity: number;
  status: string;
  applied_at: string | null;
  created_at: string;
};

export type EventOut = {
  id: number;
  type: string;
  from_status: string | null;
  to_status: string | null;
  note: string;
  created_at: string;
};

export type ApplicationDetail = ApplicationSummary & {
  job: {
    id: number;
    title: string;
    company: string;
    city: string;
    country: string;
    source_portal: string;
    url: string;
    deadline: string;
    salary_text: string;
    employment_type: string;
    role_family: string;
    jd_text: string;
    analysis: { jd: Record<string, unknown> } & Record<string, unknown>;
    created_at: string;
  };
  fit: FitScore;
  resume_variant: string;
  resume: ResumeContent | null;
  has_docx: boolean;
  has_pdf: boolean;
  pdf_note: string;
  cover_letter: string;
  email_subject: string;
  email_body: string;
  whatsapp_message: string;
  warnings: ValidationWarning[];
  high_warnings: number;
  warnings_confirmed: boolean;
  download_blocked: boolean;
  tailor_issues: string[];
  duplicates: Duplicate[];
  skip_reason: string;
  contact_name: string;
  contact_info: string;
  notes: string;
  ghost_dismissed: boolean;
  events: EventOut[];
};

export type ApplicationPatch = Partial<{
  resume: ResumeContent;
  cover_letter: string;
  email_subject: string;
  email_body: string;
  whatsapp_message: string;
  channel: Channel;
  contact_name: string;
  contact_info: string;
  notes: string;
  applied_at: string | null;
  follow_up_at: string | null;
  warnings_confirmed: boolean;
  ghost_dismissed: boolean;
}>;

export type RateRow = { key: string; applied: number; replied: number; rate: number };
export type AnalyticsSummary = {
  total: number;
  by_status: Record<string, number>;
  follow_ups_due: number;
  ghost_suggestions: number;
  per_week: { week_start: string; analysed: number; applied: number }[];
  funnel: Record<"applied" | "replied" | "interview" | "offer", number>;
  response_by_portal: RateRow[];
  response_by_role_family: RateRow[];
  response_by_resume_variant: RateRow[];
  response_by_score_band: RateRow[];
  median_days_to_first_reply: number | null;
};
export type SkillGaps = {
  jobs_analysed: number;
  missing: { skill: string; count: number }[];
  adjacent: { skill: string; count: number }[];
};

export type TruthBankDocument = { yaml: string; valid: boolean; problems: string[]; hash: string | null };
export type BaseResumeText = { role_family: string; file: string; lines: string[] };

export type ListFilters = Partial<{
  status: string;
  portal: string;
  role_family: string;
  channel: string;
  score_min: number;
  score_max: number;
  date_from: string;
  date_to: string;
  q: string;
}>;

/** An API error with the server's message (FastAPI `detail`), including truth-bank problems. */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public problems: string[] = [],
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      cache: "no-store",
      ...init,
      headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
    });
  } catch {
    throw new ApiError(0, "Can't reach the backend. Is it running on port 8000?");
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    let problems: string[] = [];
    try {
      const body = await res.json();
      const detail = body.detail;
      if (typeof detail === "string") message = detail;
      else if (detail?.message) {
        message = detail.message;
        problems = detail.problems ?? [];
      } else if (Array.isArray(detail)) message = detail.map((d) => d.msg).join("; ");
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, message, problems);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });

export function query(params: Record<string, string | number | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  analyze: (body: { jd_text: string; source_portal?: string; url?: string; tailor_despite_blockers?: boolean }) =>
    request<{ task_id: string }>("/analyze", json("POST", body)),
  task: (id: string) => request<TaskStatus>(`/analyze/${id}`),
  applications: (filters: ListFilters = {}) =>
    request<ApplicationList>(`/applications${query({ ...filters, page_size: 500 })}`),
  exportCsvUrl: (filters: ListFilters = {}) => `/api/applications/export.csv${query(filters)}`,
  application: (id: number) => request<ApplicationDetail>(`/applications/${id}`),
  update: (id: number, patch: ApplicationPatch) =>
    request<ApplicationDetail>(`/applications/${id}`, json("PATCH", patch)),
  setStatus: (id: number, status: Status, note = "") =>
    request<ApplicationDetail>(`/applications/${id}/status`, json("POST", { status, note })),
  rerender: (id: number) => request<ApplicationDetail>(`/applications/${id}/rerender`, { method: "POST" }),
  regenerate: (id: number, target: "resume" | "cover_letter") =>
    request<{ task_id: string }>(`/applications/${id}/regenerate`, json("POST", { target })),
  remove: (id: number) => request<void>(`/applications/${id}`, { method: "DELETE" }),
  downloadUrl: (id: number, fmt: "docx" | "pdf") => `/api/applications/${id}/resume.${fmt}`,
  summary: () => request<AnalyticsSummary>("/analytics/summary"),
  skillGaps: () => request<SkillGaps>("/analytics/skill-gaps"),
  truthBank: () => request<TruthBankDocument>("/truth-bank"),
  validateTruthBank: (yaml: string) => request<TruthBankDocument>("/truth-bank/validate", json("POST", { yaml })),
  saveTruthBank: (yaml: string) => request<TruthBankDocument>("/truth-bank", json("PUT", { yaml })),
  baseResumeText: (family: string) => request<BaseResumeText>(`/base-resumes/${family}/text`),
};

export async function getHealth(): Promise<HealthResponse> {
  return api.health();
}
