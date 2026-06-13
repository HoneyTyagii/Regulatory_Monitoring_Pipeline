"""Risk assessment agent: scoring, rationale, and RAG-enhanced assessment.

>>> from regmon.risk import RiskAssessmentAgent
>>> agent = RiskAssessmentAgent()
>>> assessment = agent.assess(parsed_document, classification)
>>> print(assessment.risk_level, assessment.score)
"""

from __future__ import annotations

from regmon.risk.agent import RiskAssessmentAgent
from regmon.risk.rationale import build_llm_rationale, build_rule_rationale
from regmon.risk.scoring import RiskSignals, compute_risk_score

__all__ = [
    "RiskAssessmentAgent",
    "RiskSignals",
    "build_llm_rationale",
    "build_rule_rationale",
    "compute_risk_score",
]
