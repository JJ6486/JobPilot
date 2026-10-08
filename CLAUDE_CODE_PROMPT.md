# Project brief for Claude Code: "JobPilot" (personal job-application assistant)

You are working with me (Jinash Jaleel) in my IDE to build a small, personal, single-user web app. Read this whole brief first. Then:

1. Ask me any questions you genuinely need answered. Include: my OS, and which of Python / Node / LibreOffice are installed.
2. Write a short plan and wait for my OK.

Also create a `CLAUDE.md` at the repo root that condenses the constraints, stack, and conventions below, so future sessions keep the same context.

---

## 1. Who this is for and why

I'm job hunting in Saudi Arabia for IT, software, ICT, and math-teaching roles. I apply through Indeed, Naukrigulf, Bayt.com, and some through email and WhatsApp. I've been tailoring my resume by hand for every job description (JD) and it is slow. I want a tool that does the repetitive thinking and writing, while I stay in control and do the actual applying myself in my browser.

## 2. Hard constraints (non-negotiable)

1. **Free only.** Free tools, free libraries, free API tiers. No paid services. If something would cost money, tell me and propose a free alternative.
2. **No crawling or scraping of job portals** and no browser automation against them. Job text arrives only because I paste it in (stage 1) or from sources that officially allow it (stage 2, later).
3. **No auto-applying and no auto-sending.** The app never submits an application or sends a message. I download the resume, copy the cover letter, and apply myself.
4. **Honesty guardrail.** Tailoring may only select, reorder, and rephrase things that are in my truth bank. It must never invent experience, employers, tools, certifications, years, or achievements. Skills I don't have must show up as **gaps**, never as claims. (Details in section 6.)
5. **Local-first and private.** Everything runs on my laptop. My personal details (name, phone, email, address, ID/passport numbers) are **never sent to any LLM**; they are injected locally when the resume file is rendered. The LLM only sees skills and experience content.

## 3. Stage 1 scope

User flow:

1. I paste a JD (English or Arabic) into a text box and optionally add the portal name and the job URL. I click **Start**.
2. The app does, in order:
   1. **Parse** the JD into structured data.
   2. **Duplicate check** against jobs I've already saved (warn me; let me continue anyway).
   3. **Fit score** against my truth bank, with an explanation.
   4. **Tailor** a copy of the right base resume and render a DOCX (and a PDF if possible).
   5. **Generate** a cover letter, an email subject and body, and a short WhatsApp-style message.
   6. **Save** everything to the tracker.
3. A **Review screen** shows: the score card and summary, resume diff against the base resume, validator warnings, gap list, and the cover letter. I can edit the resume text and cover letter, re-render without calling the LLM, download the DOCX/PDF, and copy the cover letter with one click.
4. I set the application status myself (Applied, Saved for later, Skip, and so on).

**The tracker is the most important part of the product.** Treat it as a first-class feature, not an afterthought (section 8).

**Stage 2 (do not build yet, but keep the architecture ready):** a "search console" that collects Saudi IT and teaching openings from allowed sources (my Gmail job-alert emails via the Gmail API read-only scope, free aggregator APIs such as Jooble or Careerjet after checking their current terms and Saudi coverage, public Greenhouse/Lever/Workable board feeds, RSS), puts them in an inbox, and lets me click "Analyze" to push one through the stage-1 pipeline.

## 4. Tech stack (all free)

- **Backend:** Python, FastAPI, Pydantic v2, SQLModel (or SQLAlchemy 2.0) on **SQLite**, Alembic for migrations, `uvicorn`.
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind + shadcn/ui, TanStack Table for the tracker table, `@dnd-kit` for the Kanban board, Recharts for analytics. Light and dark mode.
- **LLM:** a **provider abstraction** (`LLMProvider` interface) with these implementations:
  - `GeminiProvider` (default) using the official `google-genai` SDK and a free Google AI Studio API key. Use structured output with a response schema. **Check the current docs for available free-tier models and rate limits; don't hardcode a model name, read it from the `LLM_MODEL` env var and pick a sensible current Flash-class default.**
  - `OpenAICompatibleProvider` (configurable `base_url`, key, model) so I can switch to Groq, OpenRouter free models, or a local Ollama server without code changes.
  - Warn me in the README that free tiers can have data-use terms that differ from paid tiers, which is exactly why section 2.5 (PII stays local) exists.
- **Documents:** `docxtpl` (Jinja placeholders inside my own Word template, so my formatting is preserved). PDF export through headless LibreOffice **if installed** (detect it and degrade gracefully to DOCX only; show a clear message in the UI).
- **Misc:** `rapidfuzz` for near-duplicate detection, `pytest`, `ruff`, `httpx`, `python-dotenv`.
- **Dev experience:** one command to run backend and frontend together (e.g., `npm run dev` using `concurrently`), `.env.example`, and a README with Windows and macOS/Linux setup steps. Never commit secrets or personal data: add `data/` and `.env` to `.gitignore`.

## 5. Repository layout (propose changes if you have good reasons)

```
jobpilot/
  CLAUDE.md
  README.md
  .env.example
  data/                      # gitignored: my private data
    truth_bank.yaml
    base_resumes/            # software_ict.docx, teaching_math.docx (templates with placeholders)
    outputs/                 # generated resumes per application
    jobpilot.db
  backend/
    app/
      main.py
      config.py
      db/ (models.py, session.py, migrations/)
      llm/ (base.py, gemini.py, openai_compat.py, prompts/, schemas.py)
      core/ (truth_bank.py, parse_jd.py, score.py, tailor.py, cover_letter.py,
             validator.py, render_docx.py, dedupe.py, pipeline.py)
      api/ (analyze.py, applications.py, analytics.py, truth_bank.py, files.py)
      cli.py
    tests/ (fixtures/jds/*.txt, test_*.py)
  frontend/
    app/ (analyze, applications, applications/[id], analytics, truth-bank, settings)
    components/ lib/
```

## 6. Truth bank and the honesty guardrail

`data/truth_bank.yaml` is the single source of truth about me, written and edited by me. I'll provide a filled-in version based on `truth_bank.template.yaml` (supplied with this brief). Load and validate it with Pydantic on startup and show clear errors that point to the field.

Key rules:

- Every experience bullet, project, achievement, and skill has a stable `id`.
- Every skill has a `level`: `core` (used professionally), `project` (used in personal or academic projects), or `learning`. It may also have `years`, `evidence` (which bullet or project proves it), `aliases` (e.g., "JS" for "JavaScript"), and `adjacent_to` (skills it is close to, e.g., "React" is adjacent to "Vue").
- `never_claim` is a list of things I must never be shown as having.
- The `profile` block (name, phone, email, address, links) is **local-only** and is stripped before anything is sent to an LLM.

How tailoring must work (three layers of protection):

1. **Schema layer:** the LLM does not rewrite the resume freely. It returns structured JSON that **references truth-bank IDs** (which experience bullets to include and in what order, which skills to list and in what order, which projects to show). Free-text is allowed only in the professional summary and the cover letter. Bullets may be lightly reworded to mirror JD wording, but each reworded bullet must keep its `source_id`, and its facts (numbers, tools, scope) must not change.
2. **Validator layer (`validator.py`):** after generation, scan the final resume and cover letter for technology, tool, certification, employer, and number tokens that are not supported by the truth bank (use skill names + aliases + a small built-in tech-term dictionary + regex for numbers/years). Return a list of `warnings` (severity `high`/`medium`) with the offending text. High-severity warnings are shown prominently on the Review screen and block the **Download** button until I either fix the text or explicitly click "I confirm this is true."
3. **Human layer:** the diff view and editable fields on the Review screen.

Handling skills I lack:

- Required skills missing from my bank become **gaps** (listed, never inserted into the resume).
- Skills tagged `learning` may appear only in a "Currently learning" line, and only if relevant to the JD.
- For `adjacent_to` matches, the cover letter may say something honest such as "I have worked with React and am comfortable picking up Vue", but must never claim the missing tool as experience. Fit scoring gives partial credit for adjacency.

## 7. Pipeline details

Keep LLM calls **few** because of free-tier rate limits: one call to parse and score, one call to tailor and write the cover letter materials. Add: exponential backoff with jitter on 429/5xx, a visible "rate-limited, retrying" status in the UI, a request-level timeout, and caching by `(jd_hash, truth_bank_hash, prompt_version)` so re-running the same JD costs nothing. Validate all LLM output with Pydantic; on a schema failure, retry once with the validation error appended to the prompt, then fail with a clear message.

**1. Parse JD** (language-agnostic; the JD may be Arabic, English, or mixed). Extract: title, company, city/country, employment type, role family (`software_ict` | `teaching_math` | `other`), must-have skills, nice-to-have skills, minimum years of experience, education/certification requirements, **hard conditions** (e.g., "Saudi nationals only", "transferable iqama required", "Saudi teaching licence required", gender or location restrictions, "must hold valid driving licence"), salary text, deadline, contact email/phone/WhatsApp if present, and how to apply. Output English field values even if the JD is Arabic.

**2. Dedupe.** Normalised hash of (company, title, city) + canonical URL + `rapidfuzz` similarity on the JD text. Show matches with their status and date applied.

**3. Fit score.** Don't ask the LLM for a magic number. Ask it for **per-requirement judgements with evidence** (matched / adjacent / missing, and the truth-bank ID that supports each), then compute the final score deterministically in code:

- Must-have skills: 40 points
- Experience level and years: 20
- Role/title alignment: 15
- Nice-to-haves: 10
- Logistics (location, visa/iqama, licence, language): 15

Hard blockers (compared against the `constraints` block of my truth bank, such as my visa status, licence, and cities) **cap the score** and force the recommendation to `skip`, with the reason on top of the score card. Output: score 0 to 100, recommendation (`apply` | `maybe` | `skip`), a 3-line summary, matched/adjacent/missing lists, red flags, and the evidence list.

**4. Tailor resume.** Choose the base resume by `role_family`. Output the structured JSON described in section 6, rendered through the `docxtpl` template. The template must follow ATS rules: single column, standard section headings (Summary, Skills, Experience, Projects, Education, Certifications), no tables, text boxes, icons, images or multi-column layouts, a standard font, consistent dates, text-selectable output, 1 to 2 pages. Mirror the JD's exact keywords **only where true**. Name files like `Jinash_Jaleel_<Company>_<Title>_<YYYY-MM-DD>.docx`, saved under `data/outputs/<application_id>/`.

**5. Cover letter bundle.** 100 to 200 words, specific to the company and role, no clichés ("passionate", "dynamic team player"), only claims supported by the truth bank, and a configurable tone. Also produce: an email subject line, an email body (max 100 words), and a WhatsApp-style message (max 60 words). English by default, with a language option stubbed for later (Arabic).

## 8. The tracker (data model, behaviour, analytics)

Tables (SQLite; adjust types and names as you see fit, but keep the information):

- `jobs`: id, title, company, city, country, source_portal, url, posted_date, deadline, salary_text, employment_type, role_family, **jd_text (full snapshot, since postings disappear)**, jd_hash, parsed_json, created_at.
- `applications`: id, job_id, status, fit_score, recommendation, fit_breakdown_json, resume_variant, resume_content_json (the structured, editable content), resume_docx_path, resume_pdf_path, cover_letter, email_subject, email_body, whatsapp_message, channel (portal | email | whatsapp | other), applied_at, follow_up_at, contact_name, contact_info, notes, created_at, updated_at.
- `events`: id, application_id, type (created | status_change | note | edited | regenerated | reminder), from_status, to_status, note, created_at. Every change writes an event so I can see the full timeline.
- `job_requirements`: job_id, skill, kind (must | nice), result (matched | adjacent | missing). This feeds the skills-gap report.

Statuses: `saved`, `tailored`, `applied`, `replied`, `interview`, `offer`, `rejected`, `ghosted`, `skipped`, `withdrawn`.

Behaviour:

- Setting status to `applied` stamps `applied_at` and sets a default `follow_up_at` of +7 days. Show a "follow up due" badge and an "N follow-ups due" counter on the dashboard.
- Suggest `ghosted` (do not auto-apply it) after about 21 days with no reply; show a banner I can accept or dismiss.
- Table view with search, filters (status, portal, role family, score range, date range, channel), sorting, and CSV export. Kanban view with drag-and-drop between statuses (each move logs an event).
- Detail page per application: JD snapshot, score card, resume and cover letter (editable, re-render without LLM), contact, notes, timeline.

Analytics page (computed from the data, no extra LLM calls):

- Applications per week, and funnel counts (applied → replied → interview → offer).
- Response rate by portal, by role family, by resume variant, and by score band. The last one tells me whether the scoring is actually predictive.
- Median days to first reply.
- **Skills-gap report:** the most frequent `missing` and `adjacent` skills across all analysed JDs, so I know what to learn next.

## 9. API (suggested)

- `POST /api/analyze` with `{jd_text, source_portal?, url?}` starts a background task and returns `task_id`. `GET /api/analyze/{task_id}` returns progress steps (parse, dedupe, score, tailor, letter, save) and the final `application_id`. Polling is fine.
- `GET /api/applications` (filters, pagination), `GET /api/applications/{id}`, `PATCH /api/applications/{id}`, `POST /api/applications/{id}/status`, `POST /api/applications/{id}/rerender` (uses edited content, runs the validator, no LLM), `POST /api/applications/{id}/regenerate` (`resume` or `cover_letter`; uses the LLM), `GET /api/applications/{id}/resume.docx|pdf`.
- `GET /api/analytics/summary`, `GET /api/analytics/skill-gaps`.
- `GET/PUT /api/truth-bank` (validated), `GET /api/base-resumes`, `GET /api/health` (reports: LLM configured?, LibreOffice found?, truth bank valid?).
- Also provide a CLI: `python -m app.cli analyze path/to/jd.txt` that runs the whole pipeline and prints the score card and file paths. Use it to develop and test phase 1 without any UI.

## 10. Build phases (stop and show me after each one)

**Phase 0: Scaffold.** Repo layout, config, `.env.example`, health endpoint, frontend shell, one-command dev script, README, `CLAUDE.md`. *Done when:* both apps start with one command on my machine and `/api/health` renders in the UI.

**Phase 1: Core engine, CLI only.** Truth bank loader and validation, LLM provider layer, parse + score, tailor + cover letter bundle, validator, DOCX rendering (and PDF if available), dedupe. *Done when:* `python -m app.cli analyze` works end to end on at least these fixtures, and `pytest` passes: (a) a software/ICT JD, (b) a math-teaching JD, (c) a JD with a hard blocker (expect `skip` and a clear reason), (d) a JD mostly in Arabic. Tests must include: a fake `LLMProvider` returning canned JSON (so tests don't need the network); a guardrail test proving that an LLM output containing a skill not in the truth bank gets a high-severity warning; and a test that the final score is computed deterministically from the judgements.

**Phase 2: Database and tracker API.** Models, migrations, the endpoints in section 9, events, follow-up logic, dedupe wired in. *Done when:* the same flow works via API calls and the data persists across restarts.

**Phase 3: Frontend.** Analyze page (paste, Start, live progress), Review screen (score card, diff, warnings, editable resume/cover letter, download and copy buttons, status buttons), Tracker (table + Kanban + detail page with timeline), Truth-bank viewer/editor with validation errors. *Done when:* I can paste a real JD in the browser and get from "Start" to "downloaded DOCX + copied cover letter + status set to Applied" without touching the CLI.

**Phase 4: Analytics and polish.** Dashboard, analytics page, skills-gap report, CSV export, empty states, error states, rate-limit messaging, dark mode.

**Phase 5 (later, only when I ask):** the stage-2 search console.

## 11. Working agreement

- Ask before making big decisions I might care about (stack changes, new dependencies with licensing or cost implications, data-model changes after phase 2).
- Keep commits small and meaningful. Don't leave secrets or my personal data in the repo or in test fixtures; use fake personal data in tests.
- Prefer simple, readable code over clever code. Type everything (Python type hints, TypeScript strict).
- Prompts live in `backend/app/llm/prompts/` as versioned text files, not buried in code. Include the prompt version in the cache key.
- When something is unclear about my resume or background, **ask me; don't guess**.
- Tell me honestly if something I asked for is a bad idea or won't work on a free tier.

## 12. What I'll provide (I'll update these alongside this prompt)

- [ ] `data/truth_bank.yaml`, filled in from `truth_bank.template.yaml`
- [ ] `data/base_resumes/software_ict.docx` and `teaching_math.docx` (my current resumes; help me convert them into ATS-safe `docxtpl` templates with placeholders, and tell me exactly what to change)
- [ ] My free Gemini API key in `.env` (`GEMINI_API_KEY`), from Google AI Studio
- [ ] 3 to 5 real JDs (with employer details removed if you like) saved as `backend/tests/fixtures/jds/*.txt`
- [ ] My constraints: visa/iqama status, cities I'd accept, teaching licence situation, languages, minimum salary (if any). These go in the `constraints` block of the truth bank, and the fit scorer uses them.
