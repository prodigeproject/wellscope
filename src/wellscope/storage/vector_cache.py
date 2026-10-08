"""Embedding cache keyed by model and text hash.

Re-running ingest over unchanged documents then makes no embedding calls, which keeps the
one-command rebuild fast and free.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from array import array
from collections.abc import Iterator, Mapping, Sequence
from contextlib import closing, contextmanager
from pathlib import Path


def text_hash(text: str) -> str:
    """Cache key of a text."""
    return hashlib.sha256(text.encode()).hexdigest()


class VectorCache:
    """SQLite file mapping (model, text hash) to a float32 vector."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def get_many(self, model: str, hashes: Sequence[str]) -> dict[str, list[float]]:
        """Cached vectors for ``hashes``; hashes without a cached vector are omitted."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT text_hash, vector FROM vectors "
                "WHERE model = ? AND text_hash IN (SELECT value FROM json_each(?))",
                (model, json.dumps(list(hashes))),
            ).fetchall()
        return {key: array("f", blob).tolist() for key, blob in rows}

    def put_many(self, model: str, vectors: Mapping[str, Sequence[float]]) -> None:
        """Store vectors by text hash."""
        with self._connect() as connection, connection:
            connection.executemany(
                "INSERT OR REPLACE INTO vectors (model, text_hash, vector) VALUES (?, ?, ?)",
                [(model, key, array("f", vector).tobytes()) for key, vector in vectors.items()],
            )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS vectors (model TEXT NOT NULL, "
                "text_hash TEXT NOT NULL, vector BLOB NOT NULL, PRIMARY KEY (model, text_hash))"
            )
            yield connection
