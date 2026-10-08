"""On-disk cache for LLM results, keyed by (call, jd_hash, truth_bank_hash, prompt_version, model).

Re-running the same JD against the same truth bank and prompt costs no API calls.
"""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel


def text_hash(text: str) -> str:
    normalized = " ".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


class LLMCache:
    def __init__(self, directory: Path, enabled: bool = True) -> None:
        self.directory = directory
        self.enabled = enabled

    @staticmethod
    def key(*parts: str) -> str:
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]

    def get[T: BaseModel](self, key: str, schema: type[T]) -> T | None:
        path = self.directory / f"{key}.json"
        if not self.enabled or not path.is_file():
            return None
        try:
            return schema.model_validate(json.loads(path.read_text(encoding="utf-8")))
        except ValueError:
            return None  # stale or corrupt entry: treat as a miss

    def put(self, key: str, value: BaseModel) -> None:
        if not self.enabled:
            return
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / f"{key}.json").write_text(value.model_dump_json(indent=2), "utf-8")
