"""Structured output models for the classification agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class TopicTag(BaseModel):
    """A topic classification with a confidence score."""

    topic: str = Field(..., min_length=1, max_length=128)
    confidence: float = Field(..., ge=0.0, le=1.0)


class BusinessFunction(BaseModel):
    """An affected business function or department."""

    name: str = Field(..., min_length=1, max_length=128)
    relevance: float = Field(default=1.0, ge=0.0, le=1.0)


class JurisdictionConfidence(BaseModel):
    """Confidence that a document belongs to a given jurisdiction."""

    jurisdiction: str = Field(..., min_length=1, max_length=32)
    confidence: float = Field(..., ge=0.0, le=1.0)


class Classification(BaseModel):
    """Full classification result for a regulatory document."""

    topics: list[TopicTag] = Field(default_factory=list)
    business_functions: list[BusinessFunction] = Field(default_factory=list)
    jurisdiction_confidence: list[JurisdictionConfidence] = Field(default_factory=list)
    document_type: str | None = Field(
        default=None,
        max_length=64,
        description="E.g. 'circular', 'notification', 'guideline', 'regulation', 'press release'.",
    )
    urgency: str | None = Field(
        default=None,
        max_length=32,
        description="Temporal urgency: 'immediate', 'near-term', 'routine'.",
    )

    @property
    def primary_topic(self) -> str | None:
        """Highest-confidence topic, if any."""
        if not self.topics:
            return None
        return max(self.topics, key=lambda t: t.confidence).topic

    @property
    def primary_function(self) -> str | None:
        """Highest-relevance business function, if any."""
        if not self.business_functions:
            return None
        return max(self.business_functions, key=lambda f: f.relevance).name


@dataclass(frozen=True)
class ClassificationResult:
    """Wraps classification with provenance metadata."""

    document_id: str
    classification: Classification
    classifier: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = [
    "BusinessFunction",
    "Classification",
    "ClassificationResult",
    "JurisdictionConfidence",
    "TopicTag",
]
