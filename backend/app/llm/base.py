"""Provider-agnostic LLM interface plus the retry/validation loop every call goes through."""

import json
import random
import time
from abc import ABC, abstractmethod
from collections.abc import Callable

from pydantic import BaseModel, ValidationError

StatusCallback = Callable[[str], None]
MAX_HINTED_WAIT = 90.0  # never sleep longer than this on a provider's "retry in Ns" hint


class LLMError(Exception):
    """A failure that retrying won't fix (bad key, bad request, unparseable output)."""


class RetryableLLMError(LLMError):
    """Rate limit (429), server error (5xx), or timeout: worth retrying with backoff."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after  # seconds the provider asked us to wait, if it said


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> str:
        """Return the raw JSON text the model produced for `schema`."""


def _backoff_delay(attempt: int, base: float, cap: float) -> float:
    # Full jitter: uniform in [0, min(cap, base * 2^attempt)]
    return random.uniform(0, min(cap, base * (2**attempt)))


def generate_structured[T: BaseModel](
    provider: LLMProvider,
    system: str,
    user: str,
    schema: type[T],
    on_status: StatusCallback | None = None,
    max_attempts: int = 6,
    backoff_base: float = 2.0,
    backoff_cap: float = 60.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Call the provider and validate the result against `schema`.

    429/5xx/timeouts are retried with exponential backoff and jitter. If the output fails
    schema validation, the call is retried once with the validation error appended to the
    prompt; a second failure raises `LLMError`.
    """
    notify = on_status or (lambda _msg: None)
    prompt = user
    schema_retry_used = False

    while True:
        raw = _call_with_backoff(
            provider, system, prompt, schema, notify, max_attempts, backoff_base, backoff_cap, sleep
        )
        try:
            return schema.model_validate(json.loads(_strip_fences(raw)))
        except (json.JSONDecodeError, ValidationError) as exc:
            if schema_retry_used:
                raise LLMError(
                    f"{provider.name} returned output that doesn't match the "
                    f"{schema.__name__} schema twice. Last error: {exc}"
                ) from exc
            schema_retry_used = True
            notify("LLM output didn't match the schema; retrying once with the error")
            prompt = (
                f"{user}\n\nYour previous answer was invalid:\n{exc}\n"
                "Return only JSON that matches the schema exactly."
            )


def _call_with_backoff(
    provider: LLMProvider,
    system: str,
    user: str,
    schema: type[BaseModel],
    notify: StatusCallback,
    max_attempts: int,
    backoff_base: float,
    backoff_cap: float,
    sleep: Callable[[float], None],
) -> str:
    for attempt in range(max_attempts):
        try:
            return provider.complete_json(system, user, schema)
        except RetryableLLMError as exc:
            if attempt == max_attempts - 1:
                raise LLMError(
                    f"{provider.name} still failing after {max_attempts} tries: {exc}"
                ) from exc
            delay = _backoff_delay(attempt, backoff_base, backoff_cap)
            if exc.retry_after is not None:  # honour the provider's hint, plus a little jitter
                delay = min(MAX_HINTED_WAIT, exc.retry_after) + random.uniform(0.5, 2.0)
            notify(f"Rate-limited or busy ({exc}); retrying in {delay:.0f}s")
            sleep(delay)
    raise AssertionError("unreachable")


def _strip_fences(raw: str) -> str:
    """Some models wrap JSON in ```json fences even when asked not to."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()
