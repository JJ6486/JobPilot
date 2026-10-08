"""Application settings, read from the repo-root `.env` file and environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    llm_provider: Literal["gemini", "openai_compat"] = "gemini"
    llm_model: str = ""
    llm_fallback_models: str = ""  # comma-separated, tried when the main model is busy
    gemini_api_key: str = ""
    openai_compat_base_url: str = ""
    openai_compat_api_key: str = ""

    # Paths
    data_dir: Path = REPO_ROOT / "data"
    libreoffice_path: str = ""  # optional override; otherwise auto-detected

    # Server
    frontend_origin: str = "http://localhost:3000"

    @property
    def truth_bank_path(self) -> Path:
        return self.data_dir / "truth_bank.yaml"

    @property
    def base_resumes_dir(self) -> Path:
        return self.data_dir / "base_resumes"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jobpilot.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
