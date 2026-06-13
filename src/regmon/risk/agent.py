"""Risk assessment agent.

Takes a :class:`~regmon.models.ParsedDocument` (plus optional classification
and RAG context) and produces a :class:`~regmon.models.RiskAssessment` by
combining rule-based scoring with structured rationale generation.

The agent:
1. Computes a risk score from document signals (urgency, type, keywords, scope).
2. Maps the score to a :class:`~regmon.models.RiskLevel`.
3. Optionally pulls similar historical docs via RAG for contextual rationale.
4. Assembles a rationale (rule-based or LLM-enhanced).
5. Returns a complete :class:`~regmon.models.RiskAssessment`.
"""

from __future__ import annotations

from regmon.classification.models import Classification
from regmon.logging_config import get_logger
from regmon.models import ParsedDocument, RiskAssessment, RiskLevel
from regmon.rag.models import Citation, SearchRequest
from regmon.rag.service import RAGSearchService
from regmon.risk.rationale import build_llm_rationale, build_rule_rationale
from regmon.risk.scoring import RiskSignals, compute_risk_score

log = get_logger(__name__)


class RiskAssessmentAgent:
    """Produces risk assessments for regulatory documents."""

    def __init__(
        self,
        *,
        rag_service: RAGSearchService | None = None,
        rag_k: int = 3,
        assessed_by: str = "risk_assessment_agent",
    ) -> None:
        self._rag = rag_service
        self._rag_k = rag_k
        self._assessed_by = assessed_by

    def assess(
        self,
        parsed: ParsedDocument,
        classification: Classification | None = None,
    ) -> RiskAssessment:
        """Run the full risk assessment pipeline for ``parsed``.

        Parameters
        ----------
        parsed:
            The document to assess.
        classification:
            Optional pre-computed classification. If absent, scoring uses
            document text signals only.
        """
        score, signals, impacted = compute_risk_score(parsed.clean_text, classification)
        risk_level = RiskLevel.from_score(score)
        citations = self._fetch_rag_context(parsed) if self._rag else []
        rationale = self._build_rationale(parsed, risk_level, signals, classification, citations)

        assessment = RiskAssessment(
            document_id=parsed.id,
            jurisdiction=parsed.jurisdiction,
            risk_level=risk_level,
            score=score,
            confidence=self._compute_confidence(signals, classification),
            rationale=rationale,
            impacted_areas=impacted,
            assessed_by=self._assessed_by,
        )
        log.info(
            "risk.assessed",
            document_id=str(parsed.id),
            risk_level=risk_level.value,
            score=score,
            confidence=assessment.confidence,
            impacted_areas=len(impacted),
        )
        return assessment

    def _fetch_rag_context(self, parsed: ParsedDocument) -> list[Citation]:
        """Retrieve similar historical documents for contextual rationale."""
        if self._rag is None:
            return []
        try:
            query = parsed.title or parsed.clean_text[:200]
            result = self._rag.search(
                SearchRequest(
                    query=query,
                    k=self._rag_k,
                    jurisdiction=parsed.jurisdiction,
                    min_score=0.1,
                )
            )
            return result.citations
        except Exception as exc:
            log.warning("risk.rag_context_failed", error=str(exc))
            return []

    @staticmethod
    def _build_rationale(
        parsed: ParsedDocument,
        risk_level: RiskLevel,
        signals: RiskSignals,
        classification: Classification | None,
        citations: list[Citation],
    ) -> str:
        if citations:
            return build_llm_rationale(parsed, risk_level, signals, classification, citations)
        return build_rule_rationale(parsed, risk_level, signals, classification)

    @staticmethod
    def _compute_confidence(signals: RiskSignals, classification: Classification | None) -> float:
        """Heuristic confidence: higher when more signals agree."""
        signal_values = [signals.urgency, signals.doc_type, signals.keywords, signals.scope]
        nonzero = sum(1 for v in signal_values if v > 0.1)
        base = nonzero / len(signal_values)
        if classification and classification.topics:
            base = min(base + 0.1, 1.0)
        return round(base, 3)


__all__ = ["RiskAssessmentAgent"]
