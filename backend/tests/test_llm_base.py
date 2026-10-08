import json

import pytest
from pydantic import BaseModel

from app.llm.base import LLMError, LLMProvider, RetryableLLMError, generate_structured


class Answer(BaseModel):
    value: int


class ScriptedProvider(LLMProvider):
    name = "scripted"
    model = "m"

    def __init__(self, script: list[object]) -> None:
        self.script = list(script)
        self.prompts: list[str] = []

    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> str:
        self.prompts.append(user)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return str(item)


def test_retries_rate_limits_with_backoff() -> None:
    sleeps: list[float] = []
    provider = ScriptedProvider(
        [RetryableLLMError("429"), RetryableLLMError("503"), '{"value": 1}']
    )
    statuses: list[str] = []
    result = generate_structured(provider, "s", "u", Answer, statuses.append, sleep=sleeps.append)
    assert result.value == 1
    assert len(sleeps) == 2
    assert all("retrying" in s for s in statuses)


def test_honours_retry_after_hint() -> None:
    sleeps: list[float] = []
    provider = ScriptedProvider([RetryableLLMError("429", retry_after=40), '{"value": 2}'])
    generate_structured(provider, "s", "u", Answer, sleep=sleeps.append)
    assert 40 <= sleeps[0] <= 43


def test_gives_up_after_max_attempts() -> None:
    provider = ScriptedProvider([RetryableLLMError("503")] * 3)
    with pytest.raises(LLMError, match="after 3 tries"):
        generate_structured(provider, "s", "u", Answer, max_attempts=3, sleep=lambda _: None)


def test_schema_failure_retries_once_with_the_error_appended() -> None:
    provider = ScriptedProvider(['{"value": "not a number"}', '```json\n{"value": 3}\n```'])
    assert generate_structured(provider, "s", "u", Answer).value == 3
    assert "previous answer was invalid" in provider.prompts[1]


def test_second_schema_failure_raises() -> None:
    provider = ScriptedProvider(["not json", json.dumps({"wrong": 1})])
    with pytest.raises(LLMError, match="schema twice"):
        generate_structured(provider, "s", "u", Answer)
