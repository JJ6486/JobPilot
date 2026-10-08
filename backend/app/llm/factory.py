from app.config import Settings
from app.llm.base import LLMProvider
from app.llm.gemini import GeminiProvider
from app.llm.openai_compat import OpenAICompatibleProvider


def make_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "openai_compat":
        return OpenAICompatibleProvider(
            settings.openai_compat_base_url, settings.openai_compat_api_key, settings.llm_model
        )
    fallbacks = [m.strip() for m in settings.llm_fallback_models.split(",") if m.strip()]
    return GeminiProvider(settings.gemini_api_key, settings.llm_model, fallbacks)
