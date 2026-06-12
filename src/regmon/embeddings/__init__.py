"""Embeddings and vector store integration.

Chunking, embedding generation (mock/OpenAI), and pluggable vector stores
(in-memory, FAISS, Chroma), wired together by :class:`DocumentIndexer`.

>>> from regmon.embeddings import build_indexer
>>> from regmon.config import get_settings
>>> indexer = build_indexer(get_settings())
>>> indexer.index_document(parsed_document)
>>> hits = indexer.search("capital adequacy requirements", k=3)
"""

from __future__ import annotations

from pathlib import Path

from regmon.config.settings import Settings
from regmon.embeddings.chunking import Chunk, TextChunker
from regmon.embeddings.indexer import DocumentIndexer
from regmon.embeddings.providers import (
    EmbeddingProvider,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
    create_embedding_provider,
)
from regmon.embeddings.vectorstore import (
    InMemoryVectorStore,
    SearchHit,
    VectorRecord,
    VectorStore,
)


def create_vector_store(settings: Settings) -> VectorStore:
    """Build the configured vector store backend.

    ``memory`` (default) returns a persisted-if-present in-memory store; ``faiss``
    and ``chroma`` lazily import their optional backends.
    """
    backend = settings.storage.vectorstore_backend
    path = settings.storage.vectorstore_path
    if backend == "faiss":
        from regmon.embeddings.backends import FaissVectorStore

        return FaissVectorStore()
    if backend == "chroma":
        from regmon.embeddings.backends import ChromaVectorStore

        return ChromaVectorStore(path)
    return InMemoryVectorStore.load(path) if Path(path).exists() else InMemoryVectorStore()


def build_indexer(settings: Settings) -> DocumentIndexer:
    """Construct a :class:`DocumentIndexer` from settings."""
    return DocumentIndexer(create_embedding_provider(settings), create_vector_store(settings))


__all__ = [
    "Chunk",
    "DocumentIndexer",
    "EmbeddingProvider",
    "InMemoryVectorStore",
    "MockEmbeddingProvider",
    "OpenAIEmbeddingProvider",
    "SearchHit",
    "TextChunker",
    "VectorRecord",
    "VectorStore",
    "build_indexer",
    "create_embedding_provider",
    "create_vector_store",
]
