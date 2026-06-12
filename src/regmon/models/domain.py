"""Core domain models for the regulatory monitoring pipeline.

These Pydantic models define the data contracts that flow between agents:

``RegulatorySource`` -> ``RawDocument`` -> ``ParsedDocument``
-> ``RiskAssessment`` -> ``ActionItem``

Every model forbids unknown fields and strips surrounding whitespace from
strings so that malformed upstream data fails fast rather than propagating
silently through the pipeline.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)

from regmon.models.enums import (
    ActionPriority,
    ActionStatus,
    DocumentFormat,
    Jurisdiction,
    ProcessingStatus,
    RiskLevel,
    SourceType,
)


def _utcnow() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class RegMonBaseModel(BaseModel):
    """Shared base configuration for all domain models."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        use_enum_values=False,
        ser_json_timedelta="iso8601",
    )


class RegulatorySource(RegMonBaseModel):
    """A monitored origin of regulatory documents (a regulator's feed/site)."""

    id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Stable slug identifier, e.g. 'rbi-notifications'.",
    )
    name: str = Field(..., min_length=1, max_length=256)
    jurisdiction: Jurisdiction
    url: AnyUrl = Field(..., description="Entry-point URL crawled for this source.")
    source_type: SourceType
    description: str | None = Field(default=None, max_length=1024)
    enabled: bool = True
    crawl_frequency_minutes: int = Field(
        default=1440,
        ge=1,
        description="How often to poll this source, in minutes (default daily).",
    )
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)

    @field_validator("id")
    @classmethod
    def _validate_slug(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not all(ch.isalnum() or ch in "-_" for ch in normalized):
            raise ValueError(
                "id must contain only alphanumeric characters, hyphens, or underscores"
            )
        return normalized


class RawDocument(RegMonBaseModel):
    """An unprocessed document exactly as fetched from a source."""

    id: UUID = Field(default_factory=uuid4)
    source_id: str = Field(..., min_length=1, max_length=128)
    jurisdiction: Jurisdiction
    url: AnyUrl
    title: str | None = Field(default=None, max_length=512)
    content: str = Field(..., description="Raw fetched payload as decoded text.")
    content_format: DocumentFormat
    http_status: int | None = Field(default=None, ge=100, le=599)
    fetched_at: datetime = Field(default_factory=_utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def content_hash(self) -> str:
        """SHA-256 hex digest of the raw content, used for deduplication."""
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()


class ParsedDocument(RegMonBaseModel):
    """A cleaned, normalized document ready for classification and analysis."""

    id: UUID = Field(default_factory=uuid4)
    raw_document_id: UUID = Field(..., description="FK to the source RawDocument.")
    source_id: str = Field(..., min_length=1, max_length=128)
    jurisdiction: Jurisdiction
    title: str = Field(..., min_length=1, max_length=512)
    clean_text: str = Field(..., min_length=1, description="Normalized plain text.")
    summary: str | None = Field(default=None, max_length=4096)
    reference_number: str | None = Field(
        default=None,
        max_length=256,
        description="Regulator reference/circular number, e.g. 'RBI/2023-24/123'.",
    )
    language: str = Field(default="en", min_length=2, max_length=16)
    keywords: list[str] = Field(default_factory=list)
    sections: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    effective_date: datetime | None = None
    status: ProcessingStatus = ProcessingStatus.COMPLETED
    parsed_at: datetime = Field(default_factory=_utcnow)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def word_count(self) -> int:
        """Number of whitespace-delimited tokens in ``clean_text``."""
        return len(self.clean_text.split())


class RiskAssessment(RegMonBaseModel):
    """The risk evaluation produced for a parsed regulatory document."""

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID = Field(..., description="FK to the assessed ParsedDocument.")
    jurisdiction: Jurisdiction
    risk_level: RiskLevel
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Normalized risk score in [0.0, 1.0].",
    )
    confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Model confidence in the assessment.",
    )
    rationale: str = Field(..., min_length=1, max_length=8192)
    impacted_areas: list[str] = Field(default_factory=list)
    assessed_by: str = Field(
        default="risk_assessment_agent",
        min_length=1,
        max_length=128,
        description="Identifier of the agent/model that produced the assessment.",
    )
    assessed_at: datetime = Field(default_factory=_utcnow)


class ActionItem(RegMonBaseModel):
    """A concrete follow-up task generated from a risk assessment."""

    id: UUID = Field(default_factory=uuid4)
    assessment_id: UUID = Field(..., description="FK to the originating RiskAssessment.")
    title: str = Field(..., min_length=1, max_length=256)
    description: str = Field(..., min_length=1, max_length=8192)
    priority: ActionPriority
    status: ActionStatus = ActionStatus.OPEN
    owner_team: str | None = Field(default=None, max_length=128)
    due_date: datetime | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


__all__ = [
    "ActionItem",
    "ParsedDocument",
    "RawDocument",
    "RegMonBaseModel",
    "RegulatorySource",
    "RiskAssessment",
]
