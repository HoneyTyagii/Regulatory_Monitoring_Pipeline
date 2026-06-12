"""Vector store abstraction and a numpy-backed in-memory implementation.

The :class:`VectorStore` protocol decouples indexing/search from the storage
backend. :class:`InMemoryVectorStore` is the always-available default: it keeps
L2-normalized vectors in a numpy matrix (so similarity is a single matmul) and
can persist to / load from disk. FAISS and Chroma backends live in
:mod:`regmon.embeddings.backends` and are selected via configuration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class VectorRecord:
    """A vector plus its source text and metadata, addressed by ``id``."""

    id: str
    vector: list[float]
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHit:
    """A single search result."""

    id: str
    score: float
    text: str
    metadata: dict[str, Any]


@runtime_checkable
class VectorStore(Protocol):
    """Stores embedding vectors and answers similarity queries."""

    def add(self, records: list[VectorRecord]) -> None:
        """Add (or overwrite by id) a batch of vector records."""
        ...

    def query(
        self, vector: list[float], k: int = 5, where: dict[str, Any] | None = None
    ) -> list[SearchHit]:
        """Return up to ``k`` nearest records, optionally filtered by metadata."""
        ...

    def count(self) -> int:
        """Return the number of stored vectors."""
        ...


def _matches(metadata: dict[str, Any], where: dict[str, Any] | None) -> bool:
    if not where:
        return True
    return all(metadata.get(key) == value for key, value in where.items())


def _normalize(vector: list[float]) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    return arr / norm if norm else arr


class InMemoryVectorStore:
    """A numpy-backed vector store with cosine similarity and disk persistence."""

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._metadatas: list[dict[str, Any]] = []
        self._matrix: np.ndarray | None = None
        self._index: dict[str, int] = {}

    def add(self, records: list[VectorRecord]) -> None:
        for record in records:
            normalized = _normalize(record.vector)
            if record.id in self._index:
                pos = self._index[record.id]
                self._texts[pos] = record.text
                self._metadatas[pos] = dict(record.metadata)
                assert self._matrix is not None
                self._matrix[pos] = normalized
                continue
            self._index[record.id] = len(self._ids)
            self._ids.append(record.id)
            self._texts.append(record.text)
            self._metadatas.append(dict(record.metadata))
            row = normalized.reshape(1, -1)
            self._matrix = row if self._matrix is None else np.vstack([self._matrix, row])

    def query(
        self, vector: list[float], k: int = 5, where: dict[str, Any] | None = None
    ) -> list[SearchHit]:
        if self._matrix is None or not self._ids:
            return []
        q = _normalize(vector)
        scores = self._matrix @ q
        order = np.argsort(scores)[::-1]
        hits: list[SearchHit] = []
        for pos in order:
            idx = int(pos)
            if not _matches(self._metadatas[idx], where):
                continue
            hits.append(
                SearchHit(
                    id=self._ids[idx],
                    score=float(scores[idx]),
                    text=self._texts[idx],
                    metadata=self._metadatas[idx],
                )
            )
            if len(hits) >= k:
                break
        return hits

    def count(self) -> int:
        return len(self._ids)

    def persist(self, path: str | Path) -> None:
        """Persist vectors and metadata to ``path`` (a directory)."""
        directory = Path(path)
        directory.mkdir(parents=True, exist_ok=True)
        if self._matrix is not None:
            np.save(directory / "vectors.npy", self._matrix)
        (directory / "store.json").write_text(
            json.dumps(
                {"ids": self._ids, "texts": self._texts, "metadatas": self._metadatas},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, path: str | Path) -> InMemoryVectorStore:
        """Load a store previously written by :meth:`persist`."""
        directory = Path(path)
        store = cls()
        meta_file = directory / "store.json"
        if not meta_file.is_file():
            return store
        data = json.loads(meta_file.read_text(encoding="utf-8"))
        store._ids = list(data["ids"])
        store._texts = list(data["texts"])
        store._metadatas = list(data["metadatas"])
        store._index = {doc_id: i for i, doc_id in enumerate(store._ids)}
        vectors_file = directory / "vectors.npy"
        if vectors_file.is_file():
            store._matrix = np.load(vectors_file)
        return store


__all__ = ["InMemoryVectorStore", "SearchHit", "VectorRecord", "VectorStore"]
