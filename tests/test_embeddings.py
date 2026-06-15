"""Tests for embeddings, vector store, and RAG search."""

from __future__ import annotations

import uuid

from regmon.embeddings import (
    DocumentIndexer,
    InMemoryVectorStore,
    MockEmbeddingProvider,
    TextChunker,
)
from regmon.models import Jurisdiction, ParsedDocument
from regmon.rag import RAGSearchService


class TestChunking:
    def test_short_text_single_chunk(self) -> None:
        chunks = TextChunker(chunk_size=1000).split("short text")
        assert len(chunks) == 1

    def test_long_text_multiple_chunks(self) -> None:
        text = "word " * 500
        chunks = TextChunker(chunk_size=100, overlap=20).split(text)
        assert len(chunks) > 1
        # Overlap: second chunk starts before first ends
        assert chunks[1].start < chunks[0].end


class TestEmbeddings:
    def test_mock_deterministic(self) -> None:
        emb = MockEmbeddingProvider(dimension=64)
        v1 = emb.embed("hello world")
        v2 = emb.embed("hello world")
        assert v1 == v2

    def test_mock_normalized(self) -> None:
        emb = MockEmbeddingProvider(dimension=64)
        v = emb.embed("test text")
        norm = sum(x * x for x in v) ** 0.5
        assert abs(norm - 1.0) < 0.001


class TestVectorStore:
    def test_add_and_query(self) -> None:
        emb = MockEmbeddingProvider(dimension=64)
        store = InMemoryVectorStore()
        from regmon.embeddings.vectorstore import VectorRecord

        store.add(
            [
                VectorRecord(
                    id="a",
                    vector=emb.embed("banking regulation"),
                    text="banking",
                    metadata={"j": "RBI"},
                )
            ]
        )
        store.add(
            [
                VectorRecord(
                    id="b",
                    vector=emb.embed("medical device"),
                    text="medical",
                    metadata={"j": "FDA"},
                )
            ]
        )
        hits = store.query(emb.embed("bank regulation"), k=1)
        assert hits[0].id == "a"

    def test_metadata_filter(self) -> None:
        emb = MockEmbeddingProvider(dimension=64)
        store = InMemoryVectorStore()
        from regmon.embeddings.vectorstore import VectorRecord

        store.add(
            [
                VectorRecord(id="a", vector=emb.embed("text"), text="t", metadata={"j": "RBI"}),
                VectorRecord(id="b", vector=emb.embed("text"), text="t", metadata={"j": "FDA"}),
            ]
        )
        hits = store.query(emb.embed("text"), k=5, where={"j": "FDA"})
        assert all(h.metadata["j"] == "FDA" for h in hits)


class TestRAGSearch:
    def test_search_returns_citations(self) -> None:
        emb = MockEmbeddingProvider(dimension=64)
        store = InMemoryVectorStore()
        indexer = DocumentIndexer(emb, store)
        doc = ParsedDocument(
            raw_document_id=uuid.uuid4(),
            source_id="s",
            jurisdiction=Jurisdiction.RBI,
            title="Capital Adequacy",
            clean_text="Banks must maintain capital adequacy ratio under Basel norms.",
        )
        indexer.index_document(doc)
        svc = RAGSearchService(indexer)
        result = svc.query("capital adequacy", k=2)
        assert result.has_results
        assert result.citations[0].jurisdiction == "RBI"
