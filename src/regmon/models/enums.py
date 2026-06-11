"""Enumerations shared across the regulatory monitoring domain models.

All enums subclass ``str`` so they serialize to plain strings in JSON and
compare equal to their string values, which keeps API payloads and persisted
records human-readable.
"""

from __future__ import annotations

from enum import Enum


class Jurisdiction(str, Enum):
    """Regulatory body / framework a document originates from."""

    RBI = "RBI"  # Reserve Bank of India
    SEBI = "SEBI"  # Securities and Exchange Board of India
    FDA = "FDA"  # United States Food and Drug Administration
    EU_AI_ACT = "EU_AI_ACT"  # European Union Artificial Intelligence Act

    @property
    def label(self) -> str:
        """Human-friendly name for display in notifications and reports."""
        return _JURISDICTION_LABELS[self]


_JURISDICTION_LABELS: dict[Jurisdiction, str] = {
    Jurisdiction.RBI: "Reserve Bank of India",
    Jurisdiction.SEBI: "Securities and Exchange Board of India",
    Jurisdiction.FDA: "U.S. Food and Drug Administration",
    Jurisdiction.EU_AI_ACT: "European Union AI Act",
}


class RiskLevel(str, Enum):
    """Severity assigned to a regulatory change by the risk assessment agent."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def severity(self) -> int:
        """Ordinal severity (higher is more severe) for sorting/comparison."""
        return _RISK_SEVERITY[self]

    @classmethod
    def from_score(cls, score: float) -> RiskLevel:
        """Map a normalized risk score in ``[0.0, 1.0]`` to a discrete level.

        Thresholds: ``< 0.25`` low, ``< 0.5`` medium, ``< 0.75`` high,
        otherwise critical.
        """
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"score must be within [0.0, 1.0], got {score!r}")
        if score < 0.25:
            return cls.LOW
        if score < 0.5:
            return cls.MEDIUM
        if score < 0.75:
            return cls.HIGH
        return cls.CRITICAL


_RISK_SEVERITY: dict[RiskLevel, int] = {
    RiskLevel.LOW: 0,
    RiskLevel.MEDIUM: 1,
    RiskLevel.HIGH: 2,
    RiskLevel.CRITICAL: 3,
}


class SourceType(str, Enum):
    """Transport / discovery mechanism used to pull documents from a source."""

    RSS = "rss"
    HTML = "html"
    API = "api"
    SITEMAP = "sitemap"
    EMAIL = "email"


class DocumentFormat(str, Enum):
    """Original encoding of a fetched document's payload."""

    HTML = "html"
    PDF = "pdf"
    TEXT = "text"
    JSON = "json"
    XML = "xml"


class ProcessingStatus(str, Enum):
    """Lifecycle state of a document moving through the pipeline."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ActionPriority(str, Enum):
    """Urgency of a follow-up action item."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ActionStatus(str, Enum):
    """Workflow state of a follow-up action item."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    CANCELLED = "cancelled"


__all__ = [
    "ActionPriority",
    "ActionStatus",
    "DocumentFormat",
    "Jurisdiction",
    "ProcessingStatus",
    "RiskLevel",
    "SourceType",
]
