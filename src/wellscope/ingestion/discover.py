"""Find source files under the data folder, safely and independently of folder layout."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

PDF_SUFFIX = ".pdf"
DOCX_SUFFIX = ".docx"
SUPPORTED_SUFFIXES = (PDF_SUFFIX, DOCX_SUFFIX)
OFFICE_LOCK_PREFIX = "~$"
MAX_FILE_BYTES = 50 * 1024 * 1024
HASH_CHUNK_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class SourceFile:
    """A discovered file and its identity."""

    path: Path
    relative_path: str
    sha256: str
    size: int

    @property
    def is_pdf(self) -> bool:
        """Whether the file is a PDF (otherwise a Word document)."""
        return self.path.suffix.lower() == PDF_SUFFIX


@dataclass(frozen=True, slots=True)
class Rejected:
    """A file that was found but cannot be ingested."""

    relative_path: str
    reason: str
    detail: str


def discover(root: Path) -> Iterator[SourceFile | Rejected]:
    """Every PDF and Word file under ``root`` (recursively), in a stable order.

    Paths that resolve outside ``root`` (for example through symbolic links) and files over
    the size limit are rejected rather than read.
    """
    base = root.resolve()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if path.name.startswith(OFFICE_LOCK_PREFIX):
            continue
        relative = path.relative_to(root).as_posix()
        resolved = path.resolve()
        if not resolved.is_relative_to(base):
            yield Rejected(relative, "outside_data_dir", "path resolves outside the data folder")
            continue
        size = resolved.stat().st_size
        if size > MAX_FILE_BYTES:
            yield Rejected(relative, "too_large", f"{size} bytes exceeds {MAX_FILE_BYTES}")
            continue
        yield SourceFile(resolved, relative, _sha256(resolved), size)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()
