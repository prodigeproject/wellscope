"""Form templates: signatures, field labels, sections and table layouts of a report family.

Templates are YAML files shipped with the package. A report that differs only in labels, row
counts or section order is handled by editing a template, not code.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from wellscope.domain.documents import DocumentType
from wellscope.ingestion.pdf.kv import LabelSpec

FieldKind = Literal["text", "quantity", "date", "integer"]
SectionKind = Literal["kv", "table", "operations", "remarks"]
TEMPLATE_PACKAGE = "wellscope.ingestion.pdf"
TEMPLATE_FILES = ("ddr.yaml", "dgos.yaml")
PREFIX_MARK = "*"


class _Spec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FieldSpec(_Spec):
    """A labelled value and how to interpret it."""

    section: str
    labels: tuple[str, ...]
    kind: FieldKind = "text"
    heading: bool = False


class SectionSpec(_Spec):
    """A titled region of the form; ``titles`` ending in ``*`` match by prefix.

    Titles match case-sensitively so a column header such as ``Remarks`` is not mistaken for
    the ``REMARKS`` section. ``split_lines`` reads rows that have no ruling between them.
    """

    name: str
    titles: tuple[str, ...]
    kind: SectionKind = "table"
    header_rows: int = 0
    full_row: bool = False
    split_lines: bool = False

    def matches(self, title: str) -> bool:
        """Whether a cell's single line of text is one of this section's titles."""
        text = _collapse(title)
        for candidate in self.titles:
            expected = _collapse(candidate.rstrip(PREFIX_MARK))
            if text == expected or (candidate.endswith(PREFIX_MARK) and text.startswith(expected)):
                return True
        return False


class GridSpec(_Spec):
    """A small grid whose header cells sit directly above their value cells."""

    name: str
    header: tuple[str, ...]


class OperationsSpec(_Spec):
    """Layout of the daily operations table."""

    anchor: str
    columns: dict[str, str]
    npt_flag: str = "Y"
    next_day_separator: str
    footer_pattern: str


class PeriodSpec(_Spec):
    """Operational period relative to midnight of the report date."""

    start_offset_hours: int
    length_hours: int


class FormTemplate(_Spec):
    """Everything needed to parse one report family."""

    id: str
    doc_type: DocumentType
    title: str
    signatures: tuple[str, ...]
    operator_above_title: bool = False
    period: PeriodSpec
    report_number_field: str
    report_date_field: str
    well: dict[str, str]
    fields: dict[str, FieldSpec]
    sections: tuple[SectionSpec, ...] = ()
    grids: tuple[GridSpec, ...] = ()
    operations: OperationsSpec | None = None

    @model_validator(mode="after")
    def _references_exist(self) -> Self:
        referenced = {self.report_number_field, self.report_date_field, *self.well.values()}
        missing = sorted(referenced - set(self.fields))
        if missing:
            raise ValueError(f"template {self.id} references unknown fields: {missing}")
        return self

    def label_specs(self, *, heading: bool) -> tuple[LabelSpec, ...]:
        """Key-value label specs for colon labels, or for heading labels."""
        return tuple(
            LabelSpec(key, spec.labels)
            for key, spec in self.fields.items()
            if spec.heading is heading
        )


@lru_cache(maxsize=1)
def load_templates() -> tuple[FormTemplate, ...]:
    """Every packaged template, validated."""
    root = files(TEMPLATE_PACKAGE) / "templates"
    return tuple(
        parse_template((root / name).read_text(encoding="utf-8")) for name in TEMPLATE_FILES
    )


def parse_template(text: str) -> FormTemplate:
    """Validate a template written in YAML."""
    return FormTemplate.model_validate(yaml.safe_load(text))


def _collapse(text: str) -> str:
    return " ".join(text.split())
