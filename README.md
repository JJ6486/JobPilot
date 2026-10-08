# JobPilot

A personal, local-first job-application assistant. Paste a job description; JobPilot scores your
fit against your truth bank, tailors a resume and cover letter **using only facts you've written
down**, and tracks every application. It never scrapes job sites, never applies for you, and
never sends anything.

## Requirements

- Python 3.12+
- Node.js 20+
- (Optional) LibreOffice, for PDF export. Without it you get DOCX only.
- A free Google AI Studio API key (phase 1 onwards)

## Setup

### Windows (PowerShell)

```powershell
git clone <your-repo-url> JobPilot
cd JobPilot
npm run setup        # creates backend\.venv, installs Python + npm deps, creates .env
notepad .env         # add GEMINI_API_KEY
npm run dev
```

### macOS / Linux

```bash
git clone <your-repo-url> JobPilot
cd JobPilot
npm run setup
nano .env            # add GEMINI_API_KEY
npm run dev
```

Open http://localhost:3000. The dashboard's **System health** card shows what's still missing.

### Daily use

1. **Analyze**: paste a job description, pick the portal, click Start.
2. **Review**: check the score card and gaps, read the validator warnings, edit the resume and
   cover letter if needed, then **Save & re-render**. Download the DOCX/PDF and copy the cover letter.
3. Apply yourself on the portal, then click **Mark applied**. A follow-up reminder appears 7 days later.
4. **Applications** shows everything as a table or a drag-and-drop board; **Analytics** shows
   response rates and the skills you're most often missing.
API docs: http://127.0.0.1:8000/docs

### Your private data

Put these in `data/` (gitignored, never committed):

- `data/truth_bank.yaml`: everything true about you (see `data/truth_bank.template.yaml`)
- `data/base_resumes/*.docx`: your original resumes
- `data/templates/software_ict.docx`, `teaching.docx`: the same resumes with `{{ placeholders }}`
  (docxtpl). To change fonts or spacing, open these in Word and edit around the placeholders.

## Analyze a job from the command line

```bash
cd backend
.venv/Scripts/python -m app.cli check-truth-bank          # macOS/Linux: .venv/bin/python
.venv/Scripts/python -m app.cli analyze path/to/jd.txt --portal Indeed --url https://...
```

It prints the score card, gaps, validator warnings and the cover letter, saves the application
to the tracker (`data/jobpilot.db`) and the DOCX/PDF under `data/outputs/<application_id>/`.
`python -m app.cli list` shows tracked applications; `python -m app.cli status 3 applied` updates one. Re-running the same JD is free
(cached). `--force` tailors even when a hard blocker was found; `--no-cache` ignores the cache.

## API

With `npm run dev` running, interactive docs are at http://127.0.0.1:8000/docs. Main endpoints:
`POST /api/analyze` (returns a task id; poll `GET /api/analyze/{task_id}`), `GET/PATCH /api/applications/{id}`,
`POST /api/applications/{id}/status`, `/rerender`, `/regenerate`, `GET /api/applications/{id}/resume.docx|pdf`,
`GET /api/applications` (filters) and `/export.csv`, `GET /api/analytics/summary`, `/skill-gaps`,
`GET/PUT /api/truth-bank`, `GET /api/base-resumes`, `GET /api/health`.

## LibreOffice (optional, for PDF export)

JobPilot converts the generated DOCX to PDF with headless LibreOffice. It's free and open source.

**Windows**

1. Download the installer from https://www.libreoffice.org/download/download-libreoffice/ (Windows x86_64, "Fresh" or "Still" are both fine), or run `winget install TheDocumentFoundation.LibreOffice`.
2. Install with the default options. It goes to `C:\Program Files\LibreOffice\`, where JobPilot finds it automatically.
3. Restart `npm run dev` and press **Recheck** on the dashboard. LibreOffice should show **Ready**.
4. If you installed it somewhere else, set `LIBREOFFICE_PATH` in `.env` to the full path of `soffice.exe`.

**macOS**: `brew install --cask libreoffice`, or drag the app from the download page into Applications.
**Linux**: `sudo apt install libreoffice-writer` (Debian/Ubuntu) or your distro's equivalent.

Check it works: `soffice --version` (Windows: `& "C:\Program Files\LibreOffice\program\soffice.exe" --version`).

## Commands

| Command          | What it does                              |
| ---------------- | ----------------------------------------- |
| `npm run setup`  | One-time install                          |
| `npm run dev`    | Backend (:8000) and frontend (:3000)      |
| `npm test`       | Backend tests                             |
| `npm run lint`   | ruff + eslint                             |

## LLM providers and privacy

The default provider is Gemini on the **free tier**. Free tiers of LLM APIs often have
different data-use terms from paid tiers. For example, prompts may be used to improve the
provider's models. That's why JobPilot never sends your personal details (name, phone, email,
address, ID numbers, links) to any LLM. They're stripped before the call and added back locally
when the resume file is rendered. Only skills and experience content leaves your machine.

To switch providers without code changes, set `LLM_PROVIDER=openai_compat` with
`OPENAI_COMPAT_BASE_URL` / `OPENAI_COMPAT_API_KEY` / `LLM_MODEL` in `.env`. This works with Groq,
OpenRouter free models, or a fully local Ollama server.

## Project layout

```
backend/    FastAPI app (app/), tests (tests/), JD fixtures (tests/fixtures/jds/)
frontend/   Next.js app
scripts/    cross-platform setup and dev helpers
data/       your private data (gitignored)
```
