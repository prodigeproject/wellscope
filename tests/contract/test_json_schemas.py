"""The committed JSON Schemas in docs/schemas match the models that write the JSON files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wellscope.domain.schemas import json_schemas

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "docs" / "schemas"


@pytest.mark.parametrize("name", sorted(json_schemas()))
def test_committed_schema_matches_the_model(name: str) -> None:
    committed = json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
    assert committed == json_schemas()[name], "run `wellscope schema` and commit the result"


def test_every_output_file_has_a_schema() -> None:
    assert set(json_schemas()) == {"report_document", "glossary", "manifest", "quality_report"}
