"""JSON outputs of ingest (the source of truth), written atomically so readers never see a
half-written file."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from wellscope.domain.catalog import Manifest, QualityReport
from wellscope.domain.documents import ReportDocument
from wellscope.domain.glossary import Glossary

MANIFEST = "manifest.json"
GLOSSARY = "glossary.json"
QUALITY_REPORT = "quality_report.json"
DOCUMENTS_DIR = "documents"
JSON_INDENT = 2

ModelT = TypeVar("ModelT", bound=BaseModel)


class JsonStore:
    """Reads and writes the processed-data folder."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def write_document(self, document: ReportDocument) -> str:
        """Write one report; returns its path relative to the store root."""
        relative = f"{DOCUMENTS_DIR}/{document.doc_id}.json"
        self._write(relative, document)
        return relative

    def write_glossary(self, glossary: Glossary) -> str:
        """Write the glossary knowledge base."""
        self._write(GLOSSARY, glossary)
        return GLOSSARY

    def write_manifest(self, manifest: Manifest) -> None:
        """Write the catalog of this ingest run."""
        self._write(MANIFEST, manifest)

    def write_quality_report(self, report: QualityReport) -> None:
        """Write the data-quality findings."""
        self._write(QUALITY_REPORT, report)

    def prune_documents(self, keep: set[str]) -> list[str]:
        """Delete report files that the current run no longer produces."""
        removed = []
        folder = self.root / DOCUMENTS_DIR
        for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
            if path.stem not in keep:
                path.unlink()
                removed.append(path.name)
        return removed

    def read_manifest(self) -> Manifest | None:
        """The manifest, or ``None`` before the first ingest."""
        return self._read(MANIFEST, Manifest)

    def read_glossary(self) -> Glossary | None:
        """The glossary, or ``None`` when no glossary was ingested."""
        return self._read(GLOSSARY, Glossary)

    def read_document(self, doc_id: str) -> ReportDocument | None:
        """One report by id, or ``None`` when absent."""
        return self._read(f"{DOCUMENTS_DIR}/{doc_id}.json", ReportDocument)

    def read_documents(self) -> list[ReportDocument]:
        """Every report listed in the manifest."""
        manifest = self.read_manifest()
        if manifest is None:
            return []
        documents = (self.read_document(entry.doc_id) for entry in manifest.documents)
        return [document for document in documents if document is not None]

    def _write(self, relative: str, model: BaseModel) -> None:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = model.model_dump_json(indent=JSON_INDENT)
        handle, temporary = tempfile.mkstemp(dir=target.parent, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as file:
                file.write(payload)
            os.replace(temporary, target)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

    def _read(self, relative: str, model: type[ModelT]) -> ModelT | None:
        path = self.root / relative
        if not path.is_file():
            return None
        return model.model_validate_json(path.read_text(encoding="utf-8"))
