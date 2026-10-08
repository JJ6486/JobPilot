"""Versioned prompt files. A file is `<name>_v<N>.txt`: system text, `=== USER ===`, user text.

Placeholders look like `{{NAME}}` and are filled with plain string replacement, so JSON braces
in the prompts are safe. Editing a prompt file or adding a new version invalidates the LLM cache.
"""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent
SEPARATOR = "=== USER ==="


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system: str
    user: str

    @property
    def cache_id(self) -> str:
        """Version plus a hash of the text, so editing a prompt file also invalidates the cache."""
        digest = hashlib.sha256((self.system + self.user).encode("utf-8")).hexdigest()[:8]
        return f"{self.version}-{digest}"

    def render(self, **values: str) -> tuple[str, str]:
        system, user = self.system, self.user
        for key, value in values.items():
            system = system.replace("{{" + key + "}}", value)
            user = user.replace("{{" + key + "}}", value)
        return system, user


def _latest(name: str) -> Path:
    files = sorted(PROMPTS_DIR.glob(f"{name}_v*.txt"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
    if not files:
        raise FileNotFoundError(f"No prompt files for {name!r} in {PROMPTS_DIR}")
    return files[-1]


def load_prompt(name: str) -> Prompt:
    """Load the highest version of prompt `name`."""
    path = _latest(name)
    system, _, user = path.read_text(encoding="utf-8").partition(SEPARATOR)
    return Prompt(name=name, version=path.stem, system=system.strip(), user=user.strip())


def load_sections(name: str) -> tuple[str, dict[str, str]]:
    """Load a file of `=== key ===` sections (text before the first header is a comment).
    Returns (cache id, {key: text}); the cache id includes a hash of the file's text."""
    path = _latest(name)
    sections: dict[str, str] = {}
    key: str | None = None
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        header = re.fullmatch(r"=== (\w+) ===", line.strip())
        if header:
            if key:
                sections[key] = "\n".join(lines).strip()
            key, lines = header.group(1), []
        elif key:
            lines.append(line)
    if key:
        sections[key] = "\n".join(lines).strip()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
    return f"{path.stem}-{digest}", sections
