"""Rationale generation for risk assessments.

Produces a human-readable explanation of why a document received its risk level.
Two modes:

* **Rule-based** — assembles a structured rationale from the scoring signals
  and classification metadata (no LLM needed).
* **LLM-enhanced** — uses the configured LLM with RAG context from similar
  historical documents to produce a richer, contextual explanation.
"""

from __future__ import annotations

from regmon.classification.models import Classification
from regmon.models import ParsedDocument, RiskLevel
from regmon.rag.models import Citation
from regmon.risk.scoring import RiskSignals


def build_rule_rationale(
    parsed: ParsedDocument,
    risk_level: RiskLevel,
    signals: RiskSignals,
    classification: Classification | None = None,
) -> str:
    """Assemble a structured rationale from scoring signals."""
    parts: list[str] = []
    parts.append(f"Risk level: {risk_level.value.upper()} (score: {signals.composite:.3f})")
    parts.append("")

    # Urgency
    urgency = classification.urgency if classification else None
    parts.append(f"Urgency signal: {urgency or 'unknown'} (weight: {signals.urgency:.2f})")

    # Document type
    doc_type = classification.document_type if classification else None
    parts.append(f"Document type: {doc_type or 'unknown'} (weight: {signals.doc_type:.2f})")

    # Keywords
    if signals.keywords > 0:
        parts.append(f"High-risk keywords detected (weight: {signals.keywords:.2f})")

    # Scope
    if classification and classification.business_functions:
        funcs = ", ".join(f.name for f in classification.business_functions[:5])
        parts.append(f"Impacted functions ({len(classification.business_functions)}): {funcs}")

    # Penalty references
    if signals.penalty > 0:
        parts.append(f"Monetary penalty references detected (weight: {signals.penalty:.2f})")

    # Topics
    if classification and classification.topics:
        topics = ", ".join(t.topic for t in classification.topics[:5])
        parts.append(f"Topics: {topics}")

    # Jurisdiction
    parts.append(f"Jurisdiction: {parsed.jurisdiction.label}")
    if parsed.reference_number:
        parts.append(f"Reference: {parsed.reference_number}")

    return "\n".join(parts)


def build_llm_rationale(
    parsed: ParsedDocument,
    risk_level: RiskLevel,
    signals: RiskSignals,
    classification: Classification | None = None,
    rag_citations: list[Citation] | None = None,
) -> str:
    """Build a prompt-ready context for LLM rationale generation.

    When an LLM is available, this context is sent as the user message. The LLM
    produces a natural-language rationale. When no LLM is configured, this
    function falls through to :func:`build_rule_rationale`.
    """
    base = build_rule_rationale(parsed, risk_level, signals, classification)
    if not rag_citations:
        return base

    parts = [base, "", "--- Related historical documents ---"]
    for i, cit in enumerate(rag_citations[:3], 1):
        parts.append(f"[{i}] {cit.label} (similarity: {cit.score:.3f})")
        parts.append(f"    {cit.text[:200]}")
    return "\n".join(parts)


__all__ = ["build_llm_rationale", "build_rule_rationale"]
