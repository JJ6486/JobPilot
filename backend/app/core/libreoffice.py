"""Locate a headless LibreOffice (`soffice`) binary for DOCX -> PDF export."""

import shutil
import sys
from pathlib import Path

_WINDOWS_CANDIDATES = [
    Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
    Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
]
_MACOS_CANDIDATES = [Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")]


def find_soffice(override: str = "") -> Path | None:
    """Return the path to `soffice`, or None if LibreOffice is not installed."""
    if override:
        path = Path(override)
        return path if path.is_file() else None

    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return Path(found)

    candidates = _WINDOWS_CANDIDATES if sys.platform == "win32" else _MACOS_CANDIDATES
    for path in candidates:
        if path.is_file():
            return path
    return None
