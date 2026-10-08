"""Layer rules from docs/STANDARDS.md §1: inner packages never import outer adapters."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "src" / "wellscope"

FRAMEWORKS = ("fastapi", "starlette", "uvicorn", "typer")
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "domain": (
        *FRAMEWORKS,
        "openai",
        "sqlite3",
        "pdfplumber",
        "pdfminer",
        "docx",
        "numpy",
        "yaml",
        "wellscope.ingestion",
        "wellscope.storage",
        "wellscope.retrieval",
        "wellscope.llm",
        "wellscope.qa",
        "wellscope.api",
    ),
    "ingestion": (
        *FRAMEWORKS,
        "openai",
        "sqlite3",
        "wellscope.storage",
        "wellscope.retrieval",
        "wellscope.llm",
        "wellscope.qa",
        "wellscope.api",
    ),
    "storage": (
        *FRAMEWORKS,
        "openai",
        "pdfplumber",
        "wellscope.ingestion",
        "wellscope.retrieval",
        "wellscope.llm",
        "wellscope.qa",
        "wellscope.api",
    ),
    "llm": (
        *FRAMEWORKS,
        "sqlite3",
        "pdfplumber",
        "wellscope.ingestion",
        "wellscope.storage",
        "wellscope.retrieval",
        "wellscope.qa",
        "wellscope.api",
    ),
    "retrieval": (
        *FRAMEWORKS,
        "openai",
        "sqlite3",
        "pdfplumber",
        "wellscope.ingestion",
        "wellscope.storage",
        "wellscope.llm.openai_adapter",
        "wellscope.qa",
        "wellscope.api",
    ),
    "qa": (
        *FRAMEWORKS,
        "openai",
        "sqlite3",
        "pdfplumber",
        "wellscope.ingestion",
        "wellscope.storage",
        "wellscope.llm.openai_adapter",
        "wellscope.api",
    ),
}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
            modules.update(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def _violations(layer: str) -> list[str]:
    found = []
    for path in sorted((PACKAGE_ROOT / layer).rglob("*.py")):
        for module in _imported_modules(path):
            for prefix in FORBIDDEN[layer]:
                if module == prefix or module.startswith(prefix + "."):
                    found.append(f"{path.relative_to(PACKAGE_ROOT)} imports {module}")
    return found


@pytest.mark.parametrize("layer", sorted(FORBIDDEN))
def test_layer_does_not_import_forbidden_modules(layer: str) -> None:
    assert _violations(layer) == []
