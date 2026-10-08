# JobPilot

Personal, single-user, local-first job-application assistant for Jinash Jaleel (job hunting in
Saudi Arabia: software/ICT and CS/maths teaching roles). Full brief: `CLAUDE_CODE_PROMPT.md`.

## Hard constraints (never break these)

1. **Free only.** Free tools, libraries, and API tiers. If something costs money, say so and propose a free alternative.
2. **No scraping / crawling / browser automation of job portals.** JD text comes only from user paste (stage 1) or officially allowed sources (stage 2: Gmail API read-only, aggregator APIs whose terms allow it, public ATS feeds, RSS).
3. **No auto-applying or auto-sending.** The app never submits applications or sends messages.
4. **Honesty guardrail.** Tailoring may only select, reorder, and lightly rephrase truth-bank content. Never invent experience, employers, tools, certifications, years, numbers, or achievements. Missing skills are **gaps**, never claims. `learning` skills only appear in a "Currently learning" line. `adjacent_to` gives partial credit and honest wording ("comfortable picking up X"), never a claim.
5. **PII stays local.** The truth bank `profile` block (name, phone, email, location, links) and any `*_local_only` fields are stripped before anything reaches an LLM, and injected only at DOCX render time.

## Stack

- **Backend** (`backend/`): Python 3.12+ (uses PEP 695 generics), FastAPI, Pydantic v2, pydantic-settings, SQLModel on SQLite (`data/jobpilot.db`, WAL), Alembic (migrations in `app/db/migrations`, applied automatically on startup by `init_db`), uvicorn, docxtpl, rapidfuzz, pytest, ruff. Virtualenv at `backend/.venv`.
- **Frontend** (`frontend/`): Next.js 16 (App Router, Turbopack) + TypeScript strict + Tailwind v4 + shadcn/ui (radix base, `cn` package for class merging), next-themes for dark mode; TanStack Table, @dnd-kit, Recharts later. **Next 16 differs from older versions: read `frontend/node_modules/next/dist/docs/` before using an API you're unsure of** (see `frontend/AGENTS.md`).
- The browser calls `/api/*` on the Next.js origin; `frontend/next.config.ts` rewrites it to FastAPI on `127.0.0.1:8000`.
- **LLM**: `LLMProvider` interface with `GeminiProvider` (default, `google-genai` SDK, `response_json_schema` structured output) and `OpenAICompatibleProvider` (Groq / OpenRouter / Ollama). Model comes from `LLM_MODEL` (default alias `gemini-flash-latest`); `LLM_FALLBACK_MODELS` are tried when the main model returns 503/429. Free tier is ~5 requests/min per model.
- **PDF**: headless LibreOffice if found (`app/core/libreoffice.py`), else DOCX only with a clear UI message.

## Commands (run from repo root)

- `npm run setup`: one-time install (venv + pip, frontend npm, `.env` from example)
- `npm run dev`: backend (:8000) + frontend (:3000) together
- `npm test`: backend pytest
- `npm run lint`: ruff + eslint
- CLI (from `backend/`): `.venv/Scripts/python -m app.cli analyze tests/fixtures/jds/software_ict.txt [--portal X] [--url Y] [--no-cache] [--force]`, `... check-truth-bank`, `... list`, `... status <id> <status> [--note]`
- New migration after changing `app/db/models.py`: from `backend/`, `.venv/Scripts/python -m alembic revision --autogenerate -m "..."` (ask the user first: data-model changes after phase 2 need approval).

## Data

- `data/` is gitignored and private: `truth_bank.yaml`, `base_resumes/*.docx` (originals), `templates/{software_ict,teaching}.docx` (docxtpl versions cloned from the originals' own paragraphs; `_build_templates.py` regenerates them), `outputs/<application_id>/` (DOCX, PDF), `cache/` (LLM results), `backups/` (truth bank before each API save), `jobpilot.db` (tracker).
- Truth bank: every bullet/project/achievement/workshop/skill has a stable `id`. Skill `level` is `core` (used at work) / `project` / `learning`; `evidence` lists supporting ids. Sections beyond the template: `workshops`, `achievements` (`section: achievements|leadership`), project `context`/`status`/`urls`, experience `kind: work|activity` + `short_name`, role family `template`/`headline`, profile `phone_display`/`location_display`, certification `url_local_only`/`detail`. Teaching resume routing: `activity` entries with `short_name` become sub-headed roles; without it, their bullets are the intro bullets.
- Role families are **`software_ict`** and **`teaching`** (not `teaching_math`).
- JD fixtures: `backend/tests/fixtures/jds/*.txt` (see README there). Tests use `tests/fixtures/truth_bank.yaml` (fake person) and a `FakeProvider`; no network. Arabic JDs are low priority (no fixture yet).

## Pipeline rules

- Two LLM calls per JD max: (1) parse + per-requirement judgements, (2) tailor + cover letter bundle.
- Fit score is computed **deterministically in code** (`core/score.py`) from judgements: must-haves 40, experience 20, role alignment 15, nice-to-haves 10, logistics 15. Judgements whose evidence ids don't exist are downgraded (`constraints.*` may be cited for languages/visa/location). Only **eligibility** conditions block (category nationality / visa / gender / location), and only if their wording is found in the JD text; a blocker caps the score at 25, forces `skip`, and skips tailoring unless forced. Unmet qualifications, licences and degrees are **never blockers** (user's decision): they count as missing must-haves and red flags. Years of experience are scored under experience. Licence concerns only count if the JD mentions a licence.
- Tailoring keeps breadth (user's preference): start from all of a role's bullets and trim only irrelevant/duplicate ones, aiming for ~2 pages like the original resume. `MIN_WORK_BULLETS` in `core/tailor.py` tops up thin roles with original bullets.
- Resume headline = the JD's job title, cleaned to a short standard title by the tailor call (tailor v3); falls back to the role family's `headline` if empty or over 60 chars. It names the target role, not a past title.
- LLM output = structured JSON referencing truth-bank ids; reworded bullets keep `source_id` and unchanged facts. Validate with Pydantic; on failure retry once with the error appended, then fail clearly.
- `validator.py` flags unsupported tech/tool/cert/employer/number tokens; high severity blocks Download until fixed or confirmed. A reworded bullet may name tools tagged on it or used anywhere in the same job/project (its entry's bullets + skills); tools are reported once under their canonical skill name (aliases and sub-matches like "Next" in "Next.js" collapse).
- Backoff with jitter on 429/5xx (honours the provider's "retry in Ns" hint), request timeout, cache by `(jd_hash, truth_bank_hash, prompt cache_id, model)` (+ analysis hash for tailoring). `cache_id` = file version + content hash, so editing a prompt invalidates the cache.
- Prompts live in `backend/app/llm/prompts/` as versioned text files (`analyze_vN`, `tailor_vN`, `tailor_rules_vN`); the highest N is used. Requirement names are short canonical skills (analyze v5) so the skills-gap report aggregates across jobs. Candidate name in messages is the literal `{{NAME}}`, replaced locally.

## Tracker (phase 2)

- Tables: `jobs` (full JD snapshot + `parsed_json` analysis), `applications` (status, fit, `resume_content_json`, letters, `validation_json`, `warnings_confirmed`, follow-up fields), `events` (every change), `job_requirements` (feeds the skills-gap report). Timestamps are timezone-aware UTC.
- `app/db/repository.py`: `set_status` (applied -> stamps `applied_at`, `follow_up_at` +7d), `follow_up_due`, `suggest_ghosted` (21d, never auto-applied; `ghost_dismissed`).
- The pipeline commits the job + application right after scoring, then tailors; files go to `data/outputs/<application id>/`.
- Long LLM work (`POST /api/analyze`, `/regenerate`) runs on `app/tasks.py`'s single worker thread; clients poll `GET /api/analyze/{task_id}`. Task state is in memory only.
- `PATCH /api/applications/{id}` re-validates edited text (no LLM) and resets `warnings_confirmed`; `/rerender` rebuilds DOCX/PDF; downloads return 409 while high-severity warnings are unconfirmed.
- API tests override `get_settings`, `get_provider`, `get_registry` (sync); the lifespan honours the `get_settings` override so tests never touch the real database.

## Frontend (phases 3-4)

- Pages: `/` dashboard (follow-ups, recent, health), `/analyze` (paste JD, live task progress), `/applications` (filters, TanStack Table v9 table, @dnd-kit board, CSV export), `/applications/[id]` (Review screen: score card, validator + confirm, editable resume, diff vs base resume, letters with copy, files, status, details, timeline), `/analytics` (Recharts weekly chart, funnel, response rates, skills gaps), `/truth-bank` (YAML editor with validate/save), `/settings`.
- `lib/api.ts` is the typed client (mirrors `backend/app/api/schemas.py`); `lib/hooks.ts` has `useAsync` (no sync setState in effects) and `useTask` (polls background tasks).
- TanStack Table is **v9** (`useTable` + `tableFeatures`, not v8's `useReactTable`); read `node_modules/@tanstack/react-table/skills/` before changing it. Recharts is v3, diff is v9.
- Chart colours are CSS variables `--viz-*` in `app/globals.css` (validated palette, separate dark steps). Text never uses series colours.
- After adding a route, run `npx next typegen` (from `frontend/`) so `PageProps<"/route">` types exist.
- Don't run `next build` while `next dev` is running: they share `.next/` and the dev server breaks.

## Conventions

- Simple, readable, fully typed code (Python type hints, TS strict). Match surrounding style.
- Ask before stack changes, new dependencies with cost/licence implications, or data-model changes after phase 2.
- **The user runs all git commands themselves.** Don't commit; just say what changed.
- Build in phases (see brief section 10) and stop for review after each.
- When something about the user's background is unclear, ask; don't guess.
