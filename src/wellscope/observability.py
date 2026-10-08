"""Structured JSON logging with request correlation and secret redaction."""

from __future__ import annotations

import json
import logging
import re
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")

REDACTED = "[REDACTED]"
_SECRET_PATTERNS = (
    re.compile(r"()sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"),
)
_RESERVED_ATTRS = frozenset(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
}


def redact(text: str) -> str:
    """Mask API keys and bearer tokens contained in ``text``."""
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(lambda match: match.group(1) + REDACTED, text)
    return text


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects, redacting secrets."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialise ``record`` including any ``extra=`` fields."""
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_var.get(),
            "message": redact(record.getMessage()),
        }
        for key, value in vars(record).items():
            if key not in _RESERVED_ATTRS:
                payload[key] = redact(value) if isinstance(value, str) else value
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON formatter on the root logger; safe to call more than once."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
