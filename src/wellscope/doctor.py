"""Environment diagnostics for ``wellscope doctor``; secret values are never printed."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from wellscope.config import Settings
from wellscope.errors import ModelError
from wellscope.llm.ports import ChatModel, ChatRequest, Embedder

Severity = Literal["info", "warning", "error"]
MIN_PYTHON = (3, 11)
SOURCE_SUFFIXES = (".pdf", ".docx")
PING = ChatRequest(
    system="You check that the service works.",
    user='Reply with {"ok": true}.',
    schema_name="ping",
    schema={
        "type": "object",
        "additionalProperties": False,
        "required": ["ok"],
        "properties": {"ok": {"type": "boolean"}},
    },
    max_output_tokens=32,
)


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
    count = len(_sources(settings))
    if count == 0:
        return Check("data_dir", False, "warning", f"no PDF or DOCX files in {settings.data_dir}")
    return Check("data_dir", True, "info", f"{count} source files in {settings.data_dir}")


def _index(settings: Settings) -> Check:
    index = settings.database_path
    if not index.is_file():
        return Check("index", False, "warning", "no index yet; run `wellscope ingest`")
    built = index.stat().st_mtime
    changed = [path for path in _sources(settings) if path.stat().st_mtime > built]
    if changed:
        detail = (
            f"{len(changed)} source files changed since the last ingest; run `wellscope ingest`"
        )
        return Check("index", False, "warning", detail)
    return Check("index", True, "info", f"index at {index} is up to date")


def _sources(settings: Settings) -> list[Path]:
    if not settings.data_dir.is_dir():
        return []
    return [
        path
        for path in settings.data_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
    ]


def model_checks(chat_models: Mapping[str, ChatModel], embedder: Embedder | None) -> list[Check]:
    """Call each configured model once with a tiny request (costs a fraction of a cent)."""
    checks = []
    for role, model in chat_models.items():
        try:
            model.complete(PING)
        except ModelError as error:
            detail = f"{model.model}: {error} ({error.code})"
            checks.append(Check(f"model.{role}", False, "error", detail))
        else:
            checks.append(Check(f"model.{role}", True, "info", f"{model.model} is reachable"))
    if embedder is not None:
        try:
            embedder.embed(["ping"])
        except ModelError as error:
            detail = f"{embedder.model}: {error} ({error.code})"
            checks.append(Check("model.embeddings", False, "warning", detail))
        else:
            checks.append(Check("model.embeddings", True, "info", f"{embedder.model} is reachable"))
    return checks
