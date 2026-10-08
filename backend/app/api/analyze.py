"""POST /api/analyze starts the pipeline in the background; GET polls its progress."""

from fastapi import APIRouter, HTTPException
from sqlmodel import Session

from app.api.deps import ProviderDep, RegistryDep, SettingsDep, TruthBankDep
from app.api.schemas import AnalyzeRequest, TaskCreated
from app.core.pipeline import run_pipeline
from app.db.session import get_engine
from app.tasks import TaskReporter, TaskStatus

router = APIRouter(prefix="/analyze", tags=["analyze"])


@router.post("", response_model=TaskCreated, status_code=202)
def start_analysis(
    body: AnalyzeRequest,
    settings: SettingsDep,
    tb: TruthBankDep,
    provider: ProviderDep,
    registry: RegistryDep,
) -> TaskCreated:
    def work(report: TaskReporter) -> int:
        with Session(get_engine(settings)) as session:
            result = run_pipeline(
                body.jd_text,
                tb=tb,
                provider=provider,
                settings=settings,
                session=session,
                source_portal=body.source_portal,
                url=body.url,
                use_cache=body.use_cache,
                tailor_despite_blockers=body.tailor_despite_blockers,
                on_progress=report.step,
                on_status=report.message,
            )
            return result.application_id

    return TaskCreated(task_id=registry.submit("analyze", work).id)


@router.get("/{task_id}", response_model=TaskStatus)
def analysis_status(task_id: str, registry: RegistryDep) -> TaskStatus:
    task = registry.get(task_id)
    if task is None:
        raise HTTPException(404, "Unknown task (tasks are forgotten when the server restarts)")
    return task
