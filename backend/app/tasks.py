"""In-memory background tasks for long LLM work (analyze, regenerate).

One worker thread, so LLM calls never run in parallel (free tiers allow ~5 requests/minute).
Task state lives in memory: it's lost on restart, but every result is already in SQLite.
"""

import threading
import traceback
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.db.models import now

TaskState = Literal["queued", "running", "done", "error"]


class TaskStep(BaseModel):
    step: str
    state: str
    detail: str = ""


class TaskStatus(BaseModel):
    id: str
    kind: str
    state: TaskState = "queued"
    steps: list[TaskStep] = []
    messages: list[str] = []  # e.g. "Rate-limited ...; retrying in 41s"
    application_id: int | None = None
    error: str | None = None
    created_at: datetime
    finished_at: datetime | None = None


class TaskReporter:
    """Handed to the work function so it can report progress."""

    def __init__(self, registry: "TaskRegistry", task_id: str) -> None:
        self._registry, self._id = registry, task_id

    def step(self, step: str, state: str, detail: str = "") -> None:
        with self._registry.lock:
            task = self._registry.tasks[self._id]
            for existing in task.steps:
                if existing.step == step:
                    existing.state, existing.detail = state, detail
                    break
            else:
                task.steps.append(TaskStep(step=step, state=state, detail=detail))

    def message(self, text: str) -> None:
        with self._registry.lock:
            self._registry.tasks[self._id].messages.append(text)

    def set_application(self, application_id: int) -> None:
        with self._registry.lock:
            self._registry.tasks[self._id].application_id = application_id


Work = Callable[[TaskReporter], int | None]  # returns the application id


class TaskRegistry:
    MAX_KEPT = 200

    def __init__(self, sync: bool = False) -> None:
        self.lock = threading.Lock()
        self.tasks: dict[str, TaskStatus] = {}
        self.sync = sync  # run work inline (tests)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jobpilot-task")

    def submit(self, kind: str, work: Work) -> TaskStatus:
        task = TaskStatus(id=uuid.uuid4().hex[:12], kind=kind, created_at=now())
        with self.lock:
            self.tasks[task.id] = task
            if len(self.tasks) > self.MAX_KEPT:  # forget the oldest finished tasks
                for old_id in [t.id for t in self.tasks.values() if t.finished_at][
                    : len(self.tasks) - self.MAX_KEPT
                ]:
                    del self.tasks[old_id]
        if self.sync:
            self._run(task.id, work)
            return self.get(task.id) or task
        self._executor.submit(self._run, task.id, work)
        return task

    def get(self, task_id: str) -> TaskStatus | None:
        with self.lock:
            task = self.tasks.get(task_id)
            return task.model_copy(deep=True) if task else None

    def _run(self, task_id: str, work: Work) -> None:
        reporter = TaskReporter(self, task_id)
        with self.lock:
            self.tasks[task_id].state = "running"
        try:
            app_id = work(reporter)
            with self.lock:
                task = self.tasks[task_id]
                task.state, task.finished_at = "done", now()
                task.application_id = app_id if app_id is not None else task.application_id
        except Exception as exc:  # report every failure to the UI instead of losing it
            traceback.print_exc()
            with self.lock:
                task = self.tasks[task_id]
                task.state, task.error, task.finished_at = "error", str(exc), now()


registry = TaskRegistry()


def get_registry() -> TaskRegistry:
    return registry
