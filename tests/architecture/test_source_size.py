"""Size budget from docs/STANDARDS.md §2: every source module stays within 300 lines."""

from __future__ import annotations

from pathlib import Path

MAX_LINES = 300
SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "wellscope"
CHECKED_SUFFIXES = (".py", ".js")


def test_source_modules_stay_within_line_budget() -> None:
    oversized = {
        str(path.relative_to(SOURCE_ROOT)): lines
        for path in SOURCE_ROOT.rglob("*")
        if path.suffix in CHECKED_SUFFIXES
        and (lines := len(path.read_text(encoding="utf-8").splitlines())) > MAX_LINES
    }
    assert oversized == {}
