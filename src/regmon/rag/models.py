"""Data models for RAG search requests and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from regmon.models import Jurisdiction


@dataclass(frozen=True)
class Citation:
    """A citable passage from the regulatory corpus."""

    document_id: str
    chunk_index: int
    text: str
    score: float
    title: str | None = None
    reference_number: str | None = None
    jurisdiction: str | None = None
    source_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        """Short human-readable label for the citation."""
        parts: list[str] = []
        if self.reference_number:
            parts.append(self.reference_number)
        elif self.title:
            parts.append(self.title[:60])
        else:
            parts.append(f"doc:{self.document_id[:8]}")
        if self.jurisdiction:
            parts.append(f"[{self.jurisdiction}]")
        return " ".join(parts)


@dataclass(frozen=True)
class SearchRequest:
    """Parameters for a RAG search query."""

    query: str
    k: int = 5
    jurisdiction: Jurisdiction | None = None
    source_id: str | None = None
    min_score: float = 0.0
    deduplicate: bool = True


@dataclass(frozen=True)
class SearchResult:
    """The assembled response from a RAG search."""

    query: str
    citations: list[Citation]
    total_chunks_scanned: int

    @property
    def has_results(self) -> bool:
        return len(self.citations) > 0

    @property
    def top_score(self) -> float:
        return self.citations[0].score if self.citations else 0.0

    def context_block(
        self, *, max_citations: int | None = None, separator: str = "\n\n---\n\n"
    ) -> str:
        """Format citations as a single context block for LLM prompts."""
        selected = self.citations[:max_citations] if max_citations else self.citations
        parts: list[str] = []
        for i, cit in enumerate(selected, 1):
            header = f"[{i}] {cit.label} (score: {cit.score:.3f})"
            parts.append(f"{header}\n{cit.text}")
        return separator.join(parts)


__all__ = ["Citation", "SearchRequest", "SearchResult"]
