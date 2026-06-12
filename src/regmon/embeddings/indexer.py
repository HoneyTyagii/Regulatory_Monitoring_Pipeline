"""Document indexer: chunk, embed, and index parsed documents for retrieval.

Ties together the chunker, an :class:`EmbeddingProvider`, and a
:class:`VectorStore`. Indexing a :class:`ParsedDocument` splits its clean text
into chunks, embeds them, and upserts one vector per chunk (keyed
``"<document_id>:<chunk_index>"``) with metadata for downstream filtering.
"""

from __future__ import annotations

from typing import Any

from regmon.embeddings.chunking import TextChunker
from regmon.embeddings.providers import EmbeddingProvider
from regmon.embeddings.vectorstore import SearchHit, VectorRecord, VectorStore
from regmon.logging_config import get_logger
from regmon.models import Jurisdiction, ParsedDocument

log = get_logger(__name__)


class DocumentIndexer:
    """Indexes parsed documents into a vector store and runs semantic search."""

    def __init__(
        self,
        embedder: EmbeddingProvider,
        store: VectorStore,
        *,
        chunker: TextChunker | None = None,
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._chunker = chunker or TextChunker()

    def index_document(self, parsed: ParsedDocument) -> list[str]:
        """Chunk, embed, and store ``parsed``; return the created chunk ids."""
        chunks = self._chunker.split(parsed.clean_text)
        if not chunks:
            return []

        vectors = self._embedder.embed_batch([chunk.text for chunk in chunks])
        records: list[VectorRecord] = []
        chunk_ids: list[str] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            chunk_id = f"{parsed.id}:{chunk.index}"
            chunk_ids.append(chunk_id)
            records.append(
                VectorRecord(
                    id=chunk_id,
                    vector=vector,
                    text=chunk.text,
                    metadata={
                        "document_id": str(parsed.id),
                        "source_id": parsed.source_id,
                        "jurisdiction": parsed.jurisdiction.value,
                        "chunk_index": chunk.index,
                        "title": parsed.title,
                        "reference_number": parsed.reference_number,
                    },
                )
            )
        self._store.add(records)
        log.info(
            "embeddings.indexed",
            document_id=str(parsed.id),
            chunks=len(records),
            jurisdiction=parsed.jurisdiction.value,
        )
        return chunk_ids

    def search(
        self,
        query: str,
        *,
        k: int = 5,
        jurisdiction: Jurisdiction | None = None,
        where: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        """Embed ``query`` and return the ``k`` most similar chunks."""
        query_vector = self._embedder.embed(query)
        filters: dict[str, Any] = dict(where or {})
        if jurisdiction is not None:
            filters["jurisdiction"] = jurisdiction.value
        return self._store.query(query_vector, k=k, where=filters or None)


__all__ = ["DocumentIndexer"]
