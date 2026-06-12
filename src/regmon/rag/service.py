"""RAG search service: semantic retrieval with citations.

Wraps :class:`~regmon.embeddings.DocumentIndexer` with query-time features:

* Multi-field filtering (jurisdiction, source_id) via metadata predicates.
* Score thresholding to suppress low-confidence noise.
* Per-document deduplication so overlapping chunks from the same document
  don't dominate the result set.
* Citation assembly with labels derived from title/reference number.
* A ready-to-use ``context_block`` method for feeding results into an LLM.
"""

from __future__ import annotations

from typing import Any

from regmon.embeddings.indexer import DocumentIndexer
from regmon.embeddings.vectorstore import SearchHit
from regmon.logging_config import get_logger
from regmon.rag.models import Citation, SearchRequest, SearchResult

log = get_logger(__name__)

#: Factor by which we over-fetch from the store before dedup/threshold filtering.
_OVERFETCH_FACTOR = 3


class RAGSearchService:
    """Semantic search over the indexed regulatory corpus with citation tracking."""

    def __init__(
        self, indexer: DocumentIndexer, *, overfetch_factor: int = _OVERFETCH_FACTOR
    ) -> None:
        self._indexer = indexer
        self._overfetch = overfetch_factor

    def search(self, request: SearchRequest) -> SearchResult:
        """Execute a semantic search and return assembled citations."""
        where = self._build_where(request)
        fetch_k = request.k * self._overfetch
        raw_hits = self._indexer.search(
            request.query,
            k=fetch_k,
            jurisdiction=request.jurisdiction,
            where=where,
        )
        total_scanned = len(raw_hits)
        filtered = self._threshold(raw_hits, request.min_score)
        if request.deduplicate:
            filtered = self._deduplicate(filtered, request.k)
        else:
            filtered = filtered[: request.k]
        citations = [self._to_citation(hit) for hit in filtered]
        log.info(
            "rag.search",
            query_len=len(request.query),
            hits_raw=total_scanned,
            hits_returned=len(citations),
            top_score=citations[0].score if citations else 0.0,
        )
        return SearchResult(
            query=request.query, citations=citations, total_chunks_scanned=total_scanned
        )

    def query(
        self,
        query: str,
        *,
        k: int = 5,
        jurisdiction: str | None = None,
        source_id: str | None = None,
        min_score: float = 0.0,
    ) -> SearchResult:
        """Convenience wrapper that constructs a :class:`SearchRequest` internally."""
        from regmon.models import Jurisdiction as J

        jur = J(jurisdiction) if jurisdiction else None
        return self.search(
            SearchRequest(
                query=query, k=k, jurisdiction=jur, source_id=source_id, min_score=min_score
            )
        )

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _build_where(request: SearchRequest) -> dict[str, Any] | None:
        where: dict[str, Any] = {}
        if request.source_id:
            where["source_id"] = request.source_id
        return where or None

    @staticmethod
    def _threshold(hits: list[SearchHit], min_score: float) -> list[SearchHit]:
        if min_score <= 0.0:
            return hits
        return [h for h in hits if h.score >= min_score]

    @staticmethod
    def _deduplicate(hits: list[SearchHit], k: int) -> list[SearchHit]:
        """Keep the best-scoring chunk per document, up to ``k`` documents."""
        seen_docs: set[str] = set()
        deduped: list[SearchHit] = []
        for hit in hits:
            doc_id = hit.metadata.get("document_id", hit.id)
            if doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            deduped.append(hit)
            if len(deduped) >= k:
                break
        return deduped

    @staticmethod
    def _to_citation(hit: SearchHit) -> Citation:
        meta = hit.metadata
        return Citation(
            document_id=meta.get("document_id", hit.id),
            chunk_index=int(meta.get("chunk_index", 0)),
            text=hit.text,
            score=hit.score,
            title=meta.get("title"),
            reference_number=meta.get("reference_number"),
            jurisdiction=meta.get("jurisdiction"),
            source_id=meta.get("source_id"),
            metadata=meta,
        )


__all__ = ["RAGSearchService"]
