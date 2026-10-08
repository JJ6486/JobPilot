"""Command-line entry point.

python -m app.cli analyze path/to/jd.txt [--portal Indeed] [--url ...] [--no-cache]
python -m app.cli check-truth-bank
"""

import argparse
import sys
from pathlib import Path

from sqlmodel import Session, col, select

from app.config import get_settings
from app.core.pipeline import PipelineResult, run_pipeline
from app.core.truth_bank import TruthBankError, load_truth_bank
from app.db.models import STATUSES, Application, Job
from app.db.repository import set_status
from app.db.session import get_engine, init_db
from app.llm.base import LLMError
from app.llm.factory import make_provider

ICONS = {"running": "..", "done": "OK", "skipped": "--", "info": "  "}


def _print_result(r: PipelineResult) -> None:
    jd, fit = r.analysis.jd, r.fit
    line = "=" * 72
    print(
        f"\n{line}\n{jd.title} | {jd.company or '?'} | {jd.city or '?'} ({r.role_family})\n{line}"
    )
    print(f"SCORE {fit.score}/100   RECOMMENDATION: {fit.recommendation.upper()}")
    if fit.blockers:
        print("BLOCKERS:")
        for b in fit.blockers:
            print(f"  ! {b}")
    b = fit.breakdown
    print(
        f"  must-haves {b.must}/40 | experience {b.experience}/20 | role {b.role}/15 | "
        f"nice {b.nice}/10 | logistics {b.logistics}/15"
    )
    for s in fit.summary:
        print(f"  > {s}")
    print(f"\nMatched:  {', '.join(fit.matched) or '-'}")
    print(f"Adjacent: {', '.join(fit.adjacent) or '-'}")
    print(f"Gaps:     {', '.join(fit.missing) or '-'}")
    if fit.red_flags:
        print("Red flags:")
        for f in fit.red_flags:
            print(f"  - {f}")
    if r.duplicates:
        print("Possible duplicates:")
        for d in r.duplicates:
            print(f"  - {d.job_id} ({d.status}): {', '.join(d.reasons)}")
    if r.validation:
        print(f"\nValidator: {len(r.validation.warnings)} warning(s)")
        for w in r.validation.warnings:
            print(f"  [{w.severity}] {w.location}: {w.text!r}: {w.message}")
    if r.tailor_issues:
        print("Tailoring notes:")
        for i in r.tailor_issues:
            print(f"  - {i}")
    print()
    if r.skip_reason:
        print(f"Not tailored. {r.skip_reason}  (use --force to tailor anyway)")
    if r.resume_docx:
        print(f"DOCX: {r.resume_docx}")
    if r.resume_pdf:
        print(f"PDF:  {r.resume_pdf}")
    elif r.pdf_note:
        print(f"PDF:  {r.pdf_note}")
    if r.letters:
        print(f"\n--- Cover letter ---\n{r.letters.cover_letter}")
        print(f"\n--- Email ---\nSubject: {r.letters.email_subject}\n\n{r.letters.email_body}")
        print(f"\n--- WhatsApp ---\n{r.letters.whatsapp_message}")
    print(f"\nLLM calls made: {r.llm_calls_made}")


def cmd_analyze(args: argparse.Namespace) -> int:
    settings = get_settings()
    tb = load_truth_bank(settings.truth_bank_path)
    provider = make_provider(settings)
    jd_text = Path(args.jd_file).read_text(encoding="utf-8")
    print(f"Using {provider.name} / {provider.model}")
    init_db(settings)
    with Session(get_engine(settings)) as session:
        result = run_pipeline(
            jd_text,
            tb=tb,
            provider=provider,
            settings=settings,
            session=session,
            source_portal=args.portal,
            url=args.url,
            use_cache=not args.no_cache,
            tailor_despite_blockers=args.force,
            on_progress=lambda step, state, detail: print(f"[{ICONS[state]}] {step:<7} {detail}"),
            on_status=lambda msg: print(f"     {msg}"),
        )
    _print_result(result)
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    settings = get_settings()
    init_db(settings)
    with Session(get_engine(settings)) as session:
        rows = session.exec(
            select(Application, Job)
            .join(Job, col(Job.id) == col(Application.job_id))
            .order_by(col(Application.id))
        ).all()
    for app, job in rows:
        applied = f" applied {app.applied_at:%Y-%m-%d}" if app.applied_at else ""
        where = f"{job.company} | {job.title}"
        print(f"#{app.id:<4} {app.status:<10} {app.fit_score:>3}  {where}{applied}")
    print(f"{len(rows)} application(s)")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    settings = get_settings()
    init_db(settings)
    with Session(get_engine(settings)) as session:
        app = session.get(Application, args.application_id)
        if app is None:
            raise ValueError(f"No application #{args.application_id}")
        set_status(session, app, args.status, args.note)
        session.add(app)
        session.commit()
        print(f"#{app.id} is now {app.status}")
    return 0


def cmd_check(_: argparse.Namespace) -> int:
    tb = load_truth_bank(get_settings().truth_bank_path)
    print(
        f"Truth bank OK: {len(tb.experience)} experience entries, {len(tb.projects)} projects, "
        f"{len(tb.skills)} skills (hash {tb.content_hash()})"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("analyze", help="Run the full pipeline on a JD text file")
    p.add_argument("jd_file")
    p.add_argument("--portal", default="", help="e.g. Indeed, Bayt, Naukrigulf, Email, WhatsApp")
    p.add_argument("--url", default="")
    p.add_argument("--no-cache", action="store_true", help="Ignore cached LLM results")
    p.add_argument("--force", action="store_true", help="Tailor even when there's a hard blocker")
    p.set_defaults(func=cmd_analyze)
    c = sub.add_parser("check-truth-bank", help="Validate data/truth_bank.yaml")
    c.set_defaults(func=cmd_check)
    ls = sub.add_parser("list", help="List tracked applications")
    ls.set_defaults(func=cmd_list)
    st = sub.add_parser("status", help="Set an application's status")
    st.add_argument("application_id", type=int)
    st.add_argument("status", choices=STATUSES)
    st.add_argument("--note", default="")
    st.set_defaults(func=cmd_status)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except TruthBankError as exc:
        print(exc, file=sys.stderr)
    except (LLMError, ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
