"""Read-only access to the search index.

Every call opens a short-lived read-only connection, so ingest can swap the file at any time
(Windows refuses to replace a file another process keeps open). Whole-table data (catalog,
glossary, conflicts, vectors) is cached until the index version changes. Lists are passed to
SQLite as one JSON parameter, so no SQL text is ever built from values.
"""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from collections.abc import Collection, Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import numpy as np
import numpy.typing as npt

from wellscope.domain.catalog import CatalogEntry, ChunkRecord, ConflictRecord
from wellscope.domain.glossary import GlossaryEntry

Hit = tuple[str, float]


class SearchIndex:
    """The SQLite index built by ``wellscope ingest``."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._snapshot: _Snapshot | None = None

    def available(self) -> bool:
        """Whether an index has been built."""
        return self.path.is_file()

    def version(self) -> str | None:
        """Index version, or ``None`` when no index exists."""
        if not self.available():
            return None
        with _read_only(self.path) as connection:
            return _meta(connection, "index_version")

    def catalog(self) -> list[CatalogEntry]:
        """Every report, oldest first."""
        return self._current().catalog

    def glossary(self) -> list[GlossaryEntry]:
        """Every glossary entry, in source order."""
        return self._current().glossary

    def conflicts(self) -> list[ConflictRecord]:
        """Facts that documents report differently."""
        return self._current().conflicts

    def embedding_model(self) -> str | None:
        """Model the chunk vectors were built with (``None`` when the index has none)."""
        vectors = self._current().vectors
        return vectors.model if vectors else None

    def rendered(self, doc_ids: Collection[str]) -> dict[str, str]:
        """Full markdown of the given reports."""
        with _read_only(self.path) as connection:
            rows = connection.execute(
                "SELECT doc_id, rendered FROM documents "
                "WHERE doc_id IN (SELECT value FROM json_each(?))",
                (_json_list(doc_ids),),
            ).fetchall()
        return {str(row["doc_id"]): str(row["rendered"]) for row in rows}

    def chunks(self, chunk_ids: Sequence[str]) -> list[ChunkRecord]:
        """Chunks by id, in the order requested (unknown ids are skipped)."""
        with _read_only(self.path) as connection:
            rows = connection.execute(
                "SELECT chunk_id, doc_id, kind, title, page, text FROM chunks "
                "WHERE chunk_id IN (SELECT value FROM json_each(?))",
                (_json_list(chunk_ids),),
            ).fetchall()
        found = {str(row["chunk_id"]): ChunkRecord(**dict(row)) for row in rows}
        return [found[chunk_id] for chunk_id in chunk_ids if chunk_id in found]

    def keyword_search(
        self, terms: Sequence[str], doc_ids: Collection[str] | None, limit: int
    ) -> list[Hit]:
        """BM25 ranking of chunks containing any term; a higher score is a better match."""
        if not terms:
            return []
        with _read_only(self.path) as connection:
            rows = connection.execute(
                "SELECT c.chunk_id, -bm25(chunks_fts) AS score "
                "FROM chunks_fts JOIN chunks c ON c.rowid = chunks_fts.rowid "
                "WHERE chunks_fts MATCH :query AND (:doc_ids IS NULL "
                "OR c.doc_id IN (SELECT value FROM json_each(:doc_ids))) "
                "ORDER BY score DESC LIMIT :limit",
                {
                    "query": " OR ".join(_phrase(term) for term in terms),
                    "doc_ids": None if doc_ids is None else _json_list(doc_ids),
                    "limit": limit,
                },
            ).fetchall()
        return [(str(row[0]), float(row[1])) for row in rows]

    def vector_search(
        self, vector: Sequence[float], doc_ids: Collection[str] | None, limit: int
    ) -> list[Hit]:
        """Cosine ranking of chunks against a query vector from ``embedding_model``."""
        vectors = self._current().vectors
        query = np.asarray(vector, dtype=np.float32)
        norm = float(np.linalg.norm(query))
        if vectors is None or norm == 0 or query.shape != vectors.matrix.shape[1:]:
            return []
        scores = vectors.matrix @ (query / norm)
        if doc_ids is not None:
            scores[~np.isin(vectors.doc_ids, list(doc_ids))] = -np.inf
        ranked = np.argsort(-scores, kind="stable")[:limit]
        return [(vectors.chunk_ids[i], float(scores[i])) for i in ranked if np.isfinite(scores[i])]

    def _current(self) -> _Snapshot:
        version = self.version()
        if self._snapshot is None or self._snapshot.version != version:
            self._snapshot = _Snapshot(self.path, version)
        return self._snapshot


@dataclass(frozen=True)
class _Vectors:
    model: str
    chunk_ids: tuple[str, ...]
    doc_ids: npt.NDArray[np.str_]
    matrix: npt.NDArray[np.float32]


class _Snapshot:
    """Index data that only changes when ingest rebuilds the file; loaded on first use."""

    def __init__(self, path: Path, version: str | None) -> None:
        self.path = path
        self.version = version

    @cached_property
    def catalog(self) -> list[CatalogEntry]:
        with _read_only(self.path) as connection:
            rows = connection.execute(
                "SELECT doc_id, doc_type, label, title, well, rig, report_number, report_date, "
                "period_start, period_end, quality_status, summary FROM documents "
                "ORDER BY report_date, doc_type, doc_id"
            ).fetchall()
        return [_catalog_entry(row) for row in rows]

    @cached_property
    def glossary(self) -> list[GlossaryEntry]:
        with _read_only(self.path) as connection:
            rows = connection.execute("SELECT * FROM glossary ORDER BY source_row").fetchall()
        return [_glossary_entry(row) for row in rows]

    @cached_property
    def conflicts(self) -> list[ConflictRecord]:
        with _read_only(self.path) as connection:
            rows = connection.execute(
                "SELECT finding_id, detail, doc_id, value FROM conflicts ORDER BY rowid"
            ).fetchall()
        grouped: dict[tuple[str, str], list[tuple[str, str]]] = {}
        for finding_id, detail, doc_id, value in rows:
            grouped.setdefault((finding_id, detail), []).append((doc_id, value))
        return [ConflictRecord(key[0], key[1], tuple(values)) for key, values in grouped.items()]

    @cached_property
    def vectors(self) -> _Vectors | None:
        with _read_only(self.path) as connection:
            model = _meta(connection, "embedding_model")
            rows = connection.execute(
                "SELECT v.chunk_id, c.doc_id, v.vector FROM chunk_vectors v "
                "JOIN chunks c USING (chunk_id) ORDER BY c.rowid"
            ).fetchall()
        if not rows or not model:
            return None
        matrix = np.vstack([np.frombuffer(row["vector"], dtype=np.float32) for row in rows])
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1
        matrix /= norms
        chunk_ids = tuple(str(row["chunk_id"]) for row in rows)
        doc_ids = np.array([str(row["doc_id"]) for row in rows])
        return _Vectors(model, chunk_ids, doc_ids, matrix)


@contextmanager
def _read_only(path: Path) -> Iterator[sqlite3.Connection]:
    uri = f"{path.resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        yield connection


def _meta(connection: sqlite3.Connection, key: str) -> str | None:
    row = connection.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return str(row[0]) if row and row[0] else None


def _json_list(values: Collection[str]) -> str:
    return json.dumps(list(values))


def _phrase(term: str) -> str:
    """Quote a term as an FTS5 phrase so its characters are never read as query syntax."""
    return '"' + term.replace('"', '""') + '"'


def _catalog_entry(row: sqlite3.Row) -> CatalogEntry:
    values = dict(row)
    report_date = values.pop("report_date")
    period_start = values.pop("period_start")
    period_end = values.pop("period_end")
    return CatalogEntry(
        **values,
        report_date=dt.date.fromisoformat(report_date) if report_date else None,
        period_start=dt.datetime.fromisoformat(period_start) if period_start else None,
        period_end=dt.datetime.fromisoformat(period_end) if period_end else None,
    )


def _glossary_entry(row: sqlite3.Row) -> GlossaryEntry:
    values = dict(row)
    values["aliases"] = json.loads(values["aliases"])
    values["senses"] = json.loads(values["senses"])
    return GlossaryEntry.model_validate(values)
