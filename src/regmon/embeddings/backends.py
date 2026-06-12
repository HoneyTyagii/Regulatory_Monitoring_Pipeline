"""Optional FAISS and Chroma vector-store backends.

These are imported lazily so the core package has no hard dependency on FAISS or
Chroma. Install the corresponding extra to use them::

    pip install -e ".[faiss]"    # FaissVectorStore
    pip install -e ".[chroma]"   # ChromaVectorStore

Both honor the same :class:`~regmon.embeddings.vectorstore.VectorStore` protocol
as the in-memory default. Cosine similarity is obtained via inner product over
L2-normalized vectors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from regmon.embeddings.vectorstore import SearchHit, VectorRecord


def _normalize(vector: list[float]) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    return arr / norm if norm else arr


class FaissVectorStore:
    """FAISS-backed vector store using a flat inner-product index.

    Metadata filtering is applied after the FAISS search by over-fetching, which
    is adequate for the moderate corpus sizes this pipeline handles.
    """

    def __init__(self, *, overfetch: int = 10) -> None:
        try:
            import faiss
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ImportError(
                'FaissVectorStore requires faiss; install with: pip install -e ".[faiss]"'
            ) from exc
        self._faiss = faiss
        self._index: Any | None = None
        self._ids: list[str] = []
        self._texts: list[str] = []
        self._metadatas: list[dict[str, Any]] = []
        self._pos: dict[str, int] = {}
        self._overfetch = overfetch

    def add(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        if self._index is None:
            dim = len(records[0].vector)
            self._index = self._faiss.IndexFlatIP(dim)
        vectors = np.vstack([_normalize(r.vector) for r in records]).astype(np.float32)
        self._index.add(vectors)
        for record in records:
            self._pos[record.id] = len(self._ids)
            self._ids.append(record.id)
            self._texts.append(record.text)
            self._metadatas.append(dict(record.metadata))

    def query(
        self, vector: list[float], k: int = 5, where: dict[str, Any] | None = None
    ) -> list[SearchHit]:
        if self._index is None or not self._ids:
            return []
        q = _normalize(vector).reshape(1, -1)
        fetch = min(len(self._ids), k * self._overfetch if where else k)
        scores, indices = self._index.search(q, fetch)
        hits: list[SearchHit] = []
        for score, idx in zip(scores[0], indices[0], strict=False):
            if idx < 0:
                continue
            metadata = self._metadatas[idx]
            if where and any(metadata.get(key) != val for key, val in where.items()):
                continue
            hits.append(SearchHit(self._ids[idx], float(score), self._texts[idx], metadata))
            if len(hits) >= k:
                break
        return hits

    def count(self) -> int:
        return len(self._ids)


class ChromaVectorStore:
    """Chroma-backed vector store using a persistent collection."""

    def __init__(self, path: str | Path, *, collection: str = "regmon") -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ImportError(
                'ChromaVectorStore requires chromadb; install with: pip install -e ".[chroma]"'
            ) from exc
        Path(path).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(path))
        self._collection = self._client.get_or_create_collection(
            name=collection, metadata={"hnsw:space": "cosine"}
        )

    def add(self, records: list[VectorRecord]) -> None:
        if not records:
            return
        self._collection.upsert(
            ids=[r.id for r in records],
            embeddings=[r.vector for r in records],
            documents=[r.text for r in records],
            metadatas=[r.metadata or {"_": ""} for r in records],
        )

    def query(
        self, vector: list[float], k: int = 5, where: dict[str, Any] | None = None
    ) -> list[SearchHit]:
        result = self._collection.query(query_embeddings=[vector], n_results=k, where=where or None)
        ids = result["ids"][0]
        distances = result["distances"][0]
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        hits: list[SearchHit] = []
        for doc_id, distance, text, metadata in zip(
            ids, distances, documents, metadatas, strict=False
        ):
            hits.append(SearchHit(doc_id, 1.0 - float(distance), text, dict(metadata or {})))
        return hits

    def count(self) -> int:
        return int(self._collection.count())


__all__ = ["ChromaVectorStore", "FaissVectorStore"]
