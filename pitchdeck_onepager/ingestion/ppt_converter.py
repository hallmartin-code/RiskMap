"""Legacy ``.ppt`` support via headless LibreOffice.

Python has no reliable pure-library reader for the binary PowerPoint format, so
the file is converted to ``.pptx`` first. If LibreOffice is unavailable the
caller gets an actionable error rather than a silent partial result.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..errors import LibreOfficeUnavailableError
from ..logging_setup import get_logger

log = get_logger("ingestion.ppt")

_CANDIDATE_BINARIES = ("soffice", "libreoffice")
_WINDOWS_PATHS = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)
_CONVERSION_TIMEOUT_SECONDS = 180


def find_libreoffice(explicit_path: str | None = None) -> str | None:
    """Locate a usable LibreOffice binary, or return ``None``."""
    if explicit_path and Path(explicit_path).exists():
        return explicit_path
    for name in _CANDIDATE_BINARIES:
        found = shutil.which(name)
        if found:
            return found
    for candidate in _WINDOWS_PATHS:
        if Path(candidate).exists():
            return candidate
    return None


def convert_ppt_to_pptx(path: Path, temp_dir: Path, libreoffice_path: str | None = None) -> Path:
    """Convert a legacy ``.ppt`` to ``.pptx`` and return the new file path."""
    binary = find_libreoffice(libreoffice_path)
    if binary is None:
        raise LibreOfficeUnavailableError(f"Cannot convert '{path.name}': LibreOffice was not found.")

    temp_dir.mkdir(parents=True, exist_ok=True)
    command = [
        binary,
        "--headless",
        "--norestore",
        "--convert-to",
        "pptx",
        "--outdir",
        str(temp_dir),
        str(path),
    ]
    log.info("Converting legacy .ppt via LibreOffice: %s", path.name)

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=_CONVERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise LibreOfficeUnavailableError(
            f"LibreOffice timed out converting '{path.name}'."
        ) from exc
    except OSError as exc:  # pragma: no cover - permissions / exec failures
        raise LibreOfficeUnavailableError(f"Could not run LibreOffice: {exc}") from exc

    converted = temp_dir / f"{path.stem}.pptx"
    if not converted.exists():
        detail = (result.stderr or result.stdout or "").strip()[:300]
        raise LibreOfficeUnavailableError(
            f"LibreOffice did not produce a .pptx for '{path.name}'. {detail}".strip()
        )
    return converted
