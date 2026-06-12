"""RAG search service: semantic retrieval over the regulatory corpus.

>>> from regmon.rag import RAGSearchService
>>> from regmon.embeddings import build_indexer
>>> from regmon.config import get_settings
>>> service = RAGSearchService(build_indexer(get_settings()))
>>> result = service.query("capital adequacy requirements for banks", k=3)
>>> for cit in result.citations:
...     print(cit.label, cit.score)
"""

from __future__ import annotations

from regmon.rag.models import Citation, SearchRequest, SearchResult
from regmon.rag.service import RAGSearchService

__all__ = [
    "Citation",
    "RAGSearchService",
    "SearchRequest",
    "SearchResult",
]
