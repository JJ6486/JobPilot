"""LLM call 1: parse the JD and judge every requirement against the truth bank."""

import json
from datetime import date

from app.core.truth_bank import TruthBank
from app.llm.base import LLMProvider, StatusCallback, generate_structured
from app.llm.cache import LLMCache, text_hash
from app.llm.prompts import load_prompt
from app.llm.schemas import AnalysisResult


def analyze_jd(
    provider: LLMProvider,
    jd_text: str,
    tb: TruthBank,
    cache: LLMCache,
    on_status: StatusCallback | None = None,
    today: date | None = None,
) -> tuple[AnalysisResult, bool]:
    """Return (analysis, from_cache)."""
    prompt = load_prompt("analyze")
    key = cache.key(
        "analyze", text_hash(jd_text), tb.content_hash(), prompt.cache_id, provider.model
    )
    if (cached := cache.get(key, AnalysisResult)) is not None:
        return cached, True

    system, user = prompt.render(
        TODAY=(today or date.today()).isoformat(),
        TRUTH_BANK=json.dumps(tb.llm_view(), ensure_ascii=False),
        JD_TEXT=jd_text.strip(),
    )
    result = generate_structured(provider, system, user, AnalysisResult, on_status)
    cache.put(key, result)
    return result, False
