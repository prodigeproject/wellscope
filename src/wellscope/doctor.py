"""Environment diagnostics for ``wellscope doctor``; secret values are never printed."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Literal

from wellscope.config import Settings

Severity = Literal["info", "warning", "error"]
MIN_PYTHON = (3, 11)
SOURCE_SUFFIXES = (".pdf", ".docx")


@dataclass(frozen=True, slots=True)
class Check:
    """Outcome of one diagnostic check."""

    id: str
    ok: bool
    severity: Severity
    detail: str


def run_checks(settings: Settings) -> list[Check]:
    """Run every offline check against ``settings``."""
    return [
        _python_version(),
        _api_key(settings),
        _data_dir(settings),
        _index(settings),
    ]


def _python_version() -> Check:
    version = ".".join(str(part) for part in sys.version_info[:3])
    ok = sys.version_info[:2] >= MIN_PYTHON
    return Check("python", ok, "info" if ok else "error", f"Python {version}")


def _api_key(settings: Settings) -> Check:
    if settings.openai_api_key is None or not settings.openai_api_key.get_secret_value():
        return Check("api_key", False, "error", "OPENAI_API_KEY is not set (see .env.example)")
    return Check("api_key", True, "info", "OPENAI_API_KEY is set (value hidden)")


def _data_dir(settings: Settings) -> Check:
    if not settings.data_dir.is_dir():
        return Check("data_dir", False, "warning", f"{settings.data_dir} does not exist")
    count = sum(
        1 for path in settings.data_dir.rglob("*") if path.suffix.lower() in SOURCE_SUFFIXES
    )
    if count == 0:
        return Check("data_dir", False, "warning", f"no PDF or DOCX files in {settings.data_dir}")
    return Check("data_dir", True, "info", f"{count} source files in {settings.data_dir}")


def _index(settings: Settings) -> Check:
    if not settings.database_path.is_file():
        return Check("index", False, "warning", "no index yet; run `wellscope ingest`")
    return Check("index", True, "info", f"index at {settings.database_path}")
