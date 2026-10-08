"""FastAPI dependencies shared by the routers."""

from typing import Annotated

from fastapi import Depends, HTTPException

from app.config import Settings, get_settings
from app.core.truth_bank import TruthBank, TruthBankError, load_truth_bank
from app.llm.base import LLMError, LLMProvider
from app.llm.factory import make_provider
from app.tasks import TaskRegistry, get_registry

SettingsDep = Annotated[Settings, Depends(get_settings)]
RegistryDep = Annotated[TaskRegistry, Depends(get_registry)]


def get_truth_bank(settings: SettingsDep) -> TruthBank:
    """Loaded per request (it's small) so edits take effect immediately."""
    try:
        return load_truth_bank(settings.truth_bank_path)
    except TruthBankError as exc:
        raise HTTPException(
            422, {"message": "Truth bank is invalid", "problems": exc.problems}
        ) from exc


def get_provider(settings: SettingsDep) -> LLMProvider:
    try:
        return make_provider(settings)
    except LLMError as exc:
        raise HTTPException(503, str(exc)) from exc


TruthBankDep = Annotated[TruthBank, Depends(get_truth_bank)]
ProviderDep = Annotated[LLMProvider, Depends(get_provider)]
