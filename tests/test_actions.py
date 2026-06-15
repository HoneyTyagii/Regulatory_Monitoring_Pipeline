"""Tests for the action planner agent."""

from __future__ import annotations

from regmon.actions import ActionPlannerAgent
from regmon.classification import ClassificationAgent
from regmon.models import ActionPriority, RiskLevel
from regmon.risk import RiskAssessmentAgent


class TestActionPlanner:
    def test_high_risk_generates_escalation(self, parsed_document) -> None:
        cls = ClassificationAgent().classify(parsed_document).classification
        assessment = RiskAssessmentAgent().assess(parsed_document, cls)
        planner = ActionPlannerAgent()
        items = planner.plan(parsed_document, assessment, cls)
        assert len(items) >= 3
        assert any("Escalate" in item.title for item in items)
        assert all(item.priority in (ActionPriority.HIGH, ActionPriority.URGENT) for item in items)
        assert all(item.due_date is not None for item in items)
        assert all(item.owner_team for item in items)

    def test_low_risk_generates_acknowledgement(self) -> None:
        import uuid

        from regmon.models import Jurisdiction, ParsedDocument, RiskAssessment

        doc = ParsedDocument(
            raw_document_id=uuid.uuid4(),
            source_id="s",
            jurisdiction=Jurisdiction.RBI,
            title="Info",
            clean_text="General information notice.",
        )
        assessment = RiskAssessment(
            document_id=doc.id,
            jurisdiction=Jurisdiction.RBI,
            risk_level=RiskLevel.LOW,
            score=0.1,
            rationale="Low risk.",
        )
        planner = ActionPlannerAgent()
        items = planner.plan(doc, assessment)
        assert len(items) >= 1
        assert any("Acknowledge" in item.title for item in items)
        assert all(item.priority == ActionPriority.LOW for item in items)
