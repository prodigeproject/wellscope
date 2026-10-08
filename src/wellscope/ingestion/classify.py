"""Choose a form template from a document's own text, never from its file or folder name."""

from __future__ import annotations

from collections.abc import Sequence

from wellscope.ingestion.pdf.templates import FormTemplate


def classify(first_page_text: str, templates: Sequence[FormTemplate]) -> FormTemplate | None:
    """The template whose every signature appears on the first page, or ``None``."""
    text = " ".join(first_page_text.split()).casefold()
    return next(
        (
            template
            for template in templates
            if all(
                " ".join(signature.split()).casefold() in text for signature in template.signatures
            )
        ),
        None,
    )
