"""Dummy glossary content that mirrors the real glossary's structure, and a DOCX writer."""

from __future__ import annotations

from pathlib import Path

from docx import Document

# Dummy content that mirrors the structure of the real glossary (which is not committed).
GLOSSARY_TABLES = [
    [
        ["Part", "Meaning"],
        ["ALPHA", "Field name. The well targets reservoirs below the Beta field."],
        ["-2", "Well number 2."],
    ],
    [
        ["Abbreviation", "Meaning"],
        ["A", "A"],
        ["ABC", "Alpha Bravo Charlie – Example definition of a term."],
        ["Avg.", "Average"],
        ["QQ", "Unknown – Seen in a report field. (to be confirmed)"],
        ["K1 / K2", "Phase codes – Codes in the operation table. (to be confirmed)"],
        ["X/Y", "Cross Yield – A term whose abbreviation contains a slash."],
        ["kgs", "Kilograms – Written 'Kgs' by mistake in the report."],
        ["Z", "Z"],
        [
            "ZZ",
            "Zone Zero / Zig Zag – Zone Zero in the report glossary; Zig Zag in the log viewer.",
        ],
    ],
]


def write_docx(path: Path, tables: list[list[list[str]]]) -> Path:
    """Save ``tables`` (rows of cell texts) as a Word document."""
    document = Document()
    for rows in tables:
        table = document.add_table(rows=len(rows), cols=len(rows[0]))
        for row, values in zip(table.rows, rows, strict=True):
            for cell, value in zip(row.cells, values, strict=True):
                cell.text = value
    document.save(str(path))
    return path
