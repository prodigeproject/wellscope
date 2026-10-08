"""JSON Schemas of the files ``wellscope ingest`` writes (published in docs/schemas)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from wellscope.domain.catalog import Manifest, QualityReport
from wellscope.domain.documents import ReportDocument
from wellscope.domain.glossary import Glossary

SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "report_document": ReportDocument,
    "glossary": Glossary,
    "manifest": Manifest,
    "quality_report": QualityReport,
}


def json_schemas() -> dict[str, dict[str, Any]]:
    """Schema of each output file, as written (serialisation mode)."""
    return {
        name: model.model_json_schema(mode="serialization") for name, model in SCHEMA_MODELS.items()
    }
