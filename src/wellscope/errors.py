"""Exception hierarchy; every error carries a stable, machine-readable ``code``."""

from __future__ import annotations


class WellScopeError(Exception):
    """Base class for application errors."""

    code = "wellscope_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code


class ConfigurationError(WellScopeError):
    """Settings are missing or invalid."""

    code = "configuration_error"


class IngestionError(WellScopeError):
    """A source file could not be ingested."""

    code = "ingestion_error"


class DocumentParseError(IngestionError):
    """A document was recognised but could not be parsed."""

    code = "parse_error"


class IndexNotReadyError(WellScopeError):
    """No search index exists yet; run ``wellscope ingest``."""

    code = "index_not_ready"


class ModelError(WellScopeError):
    """The language-model provider failed or returned an invalid response."""

    code = "model_error"


class RateLimitedError(WellScopeError):
    """A client exceeded the allowed request rate."""

    code = "rate_limited"
