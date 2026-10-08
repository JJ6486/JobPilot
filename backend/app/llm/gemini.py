"""Google Gemini via the official google-genai SDK, using JSON-schema structured output."""

import re

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from app.llm.base import LLMError, LLMProvider, RetryableLLMError

DEFAULT_MODEL = "gemini-flash-latest"  # alias that tracks the newest Flash model
_RETRY_HINT = re.compile(r"retry in ([\d.]+)\s*s|retryDelay['\"]?:\s*['\"]?([\d.]+)s", re.I)


def _retry_after(exc: Exception) -> float | None:
    """Gemini's 429s say how long to wait ("Please retry in 41.4s"); use it."""
    match = _RETRY_HINT.search(str(exc))
    return float(match.group(1) or match.group(2)) if match else None


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str,
        model: str = "",
        fallback_models: list[str] | None = None,
        timeout_s: float = 120.0,
    ) -> None:
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set. Add it to .env.")
        self.model = model or DEFAULT_MODEL
        self.fallback_models = [m for m in (fallback_models or []) if m and m != self.model]
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=int(timeout_s * 1000))
        )

    def complete_json(self, system: str, user: str, schema: type[BaseModel]) -> str:
        """Try the main model; if it's overloaded (503) or out of quota (429), try each
        fallback model once before reporting a retryable error."""
        last: RetryableLLMError | None = None
        for model in [self.model, *self.fallback_models]:
            try:
                return self._generate(model, system, user, schema)
            except RetryableLLMError as exc:
                last = exc
        assert last is not None
        raise last

    def _generate(self, model: str, system: str, user: str, schema: type[BaseModel]) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
            response_mime_type="application/json",
            response_json_schema=schema.model_json_schema(),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            response = self._client.models.generate_content(
                model=model, contents=user, config=config
            )
        except errors.APIError as exc:
            if exc.code == 429 or exc.code >= 500:
                reason = "quota exceeded" if exc.code == 429 else "model busy"
                raise RetryableLLMError(
                    f"{model}: HTTP {exc.code} ({reason})", retry_after=_retry_after(exc)
                ) from exc
            raise LLMError(f"Gemini HTTP {exc.code}: {exc.message}") from exc
        except Exception as exc:  # httpx timeouts/transport errors surface as various types
            if "timeout" in type(exc).__name__.lower() or "timed out" in str(exc).lower():
                raise RetryableLLMError(f"{model}: request timed out") from exc
            raise
        if not response.text:
            raise LLMError(
                "Gemini returned an empty response (possibly blocked by safety filters)."
            )
        return response.text
