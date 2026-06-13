"""Pipeline context: carries per-document state through the processing graph."""

from __future__ import annotations

from dataclasses import dataclass, field

from regmon.classification.models import ClassificationResult
from regmon.models import ActionItem, ParsedDocument, RawDocument, RiskAssessment
from regmon.summarization.models import SummarizationResult


@dataclass
class DocumentContext:
    """All processing artifacts for a single document flowing through the pipeline."""

    raw: RawDocument
    parsed: ParsedDocument | None = None
    classification: ClassificationResult | None = None
    summarization: SummarizationResult | None = None
    risk_assessment: RiskAssessment | None = None
    action_items: list[ActionItem] = field(default_factory=list)
    is_duplicate: bool = False
    error: str | None = None

    @property
    def document_id(self) -> str:
        return str(self.raw.id)

    @property
    def is_processed(self) -> bool:
        return self.parsed is not None and self.risk_assessment is not None


@dataclass
class PipelineRunContext:
    """Top-level context for an entire pipeline run."""

    run_id: str
    documents: list[DocumentContext] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    @property
    def processed_count(self) -> int:
        return sum(1 for d in self.documents if d.is_processed)

    @property
    def duplicate_count(self) -> int:
        return sum(1 for d in self.documents if d.is_duplicate)

    @property
    def error_count(self) -> int:
        return len(self.errors)


__all__ = ["DocumentContext", "PipelineRunContext"]
