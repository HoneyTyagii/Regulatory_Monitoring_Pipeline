"""Tests for risk assessment agent."""

from __future__ import annotations

from regmon.classification import ClassificationAgent
from regmon.models import RiskLevel
from regmon.risk import RiskAssessmentAgent, compute_risk_score


class TestScoring:
    def test_high_risk_keywords(self) -> None:
        score, signals, _ = compute_risk_score(
            "RBI prohibits all banks with immediate effect. Non-compliance attracts "
            "penalty of Rs. 5 crore. License revocation may follow."
        )
        assert score > 0.3
        assert signals.keywords > 0

    def test_low_risk_text(self) -> None:
        score, _, _ = compute_risk_score("Annual report of the committee was released.")
        assert score < 0.3


class TestRiskAssessmentAgent:
    def test_assess_high_risk(self, parsed_document) -> None:
        cls = ClassificationAgent().classify(parsed_document).classification
        agent = RiskAssessmentAgent()
        assessment = agent.assess(parsed_document, cls)
        assert assessment.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
        assert assessment.score > 0.4
        assert len(assessment.rationale) > 10
        assert assessment.impacted_areas

    def test_assess_low_risk(self) -> None:
        import uuid

        from regmon.models import Jurisdiction, ParsedDocument

        doc = ParsedDocument(
            raw_document_id=uuid.uuid4(),
            source_id="s",
            jurisdiction=Jurisdiction.RBI,
            title="Essay Winners",
            clean_text="RBI announces essay competition winners at Mumbai headquarters.",
        )
        agent = RiskAssessmentAgent()
        assessment = agent.assess(doc)
        assert assessment.risk_level == RiskLevel.LOW
