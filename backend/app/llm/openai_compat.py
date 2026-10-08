"""Any OpenAI-compatible chat API: Groq, OpenRouter, a local Ollama server, ..."""

import json

import httpx
from pydantic import BaseModel

from app.llm.base import LLMError, LLMProvider, RetryableLLMError


class OpenAICompatibleProvider(LLMProvider):
    name = "openai_compat"

    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 120.0) -> None:
        if not base_url or not model:
            raise LLMError("Set OPENAI_COMPAT_BASE_URL and LLM_MODEL in .env.")
        self.model = model
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key or 'none'}"}
        self._timeout = timeout_s

    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> str:
        # Not every compatible server supports json_schema, so the schema also goes in the
        # prompt and we only ask for a JSON object; Pydantic validates the result.
        schema_text = json.dumps(schema.model_json_schema())
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": f"{system}\n\nReply with JSON matching this schema:\n{schema_text}",
                },
                {"role": "user", "content": user},
            ],
        }
        try:
            res = httpx.post(self._url, json=payload, headers=self._headers, timeout=self._timeout)
        except httpx.TimeoutException as exc:
            raise RetryableLLMError("request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"Could not reach {self._url}: {exc}") from exc
        if res.status_code == 429 or res.status_code >= 500:
            raise RetryableLLMError(f"HTTP {res.status_code}")
        if res.status_code >= 400:
            raise LLMError(f"HTTP {res.status_code}: {res.text[:300]}")
        try:
            return res.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError(f"Unexpected response shape: {res.text[:300]}") from exc
