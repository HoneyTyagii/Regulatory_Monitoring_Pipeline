"""Tests for the classification agent."""

from __future__ import annotations

from regmon.classification import ClassificationAgent, RuleBasedClassifier
from regmon.models import Jurisdiction


class TestRuleBasedClassifier:
    def test_detects_kyc_topic(self) -> None:
        cls = RuleBasedClassifier()
        result = cls.classify("KYC norms for banks and customer due diligence")
        topics = [t.topic for t in result.topics]
        assert "KYC / AML" in topics

    def test_detects_urgency_immediate(self) -> None:
        cls = RuleBasedClassifier()
        result = cls.classify("with immediate effect all banks must comply")
        assert result.urgency == "immediate"

    def test_detects_document_type(self) -> None:
        cls = RuleBasedClassifier()
        result = cls.classify("This circular is issued to all banks")
        assert result.document_type == "circular"


class TestClassificationAgent:
    def test_classify_returns_result(self, parsed_document) -> None:
        agent = ClassificationAgent()
        result = agent.classify(parsed_document)
        assert result.classification.primary_topic is not None
        assert result.classifier == "rules"

    def test_jurisdiction_always_present(self, parsed_document) -> None:
        agent = ClassificationAgent()
        result = agent.classify(parsed_document)
        jurisdictions = [j.jurisdiction for j in result.classification.jurisdiction_confidence]
        assert Jurisdiction.RBI.value in jurisdictions
