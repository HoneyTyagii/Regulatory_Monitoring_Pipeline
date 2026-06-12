"""Classification agent: topic tagging, business function mapping, jurisdiction confidence.

>>> from regmon.classification import ClassificationAgent
>>> agent = ClassificationAgent()
>>> result = agent.classify(parsed_document)
>>> print(result.classification.primary_topic)
"""

from __future__ import annotations

from regmon.classification.agent import ClassificationAgent, create_classification_agent
from regmon.classification.llm_classifier import LLMClassifier
from regmon.classification.models import (
    BusinessFunction,
    Classification,
    ClassificationResult,
    JurisdictionConfidence,
    TopicTag,
)
from regmon.classification.rules import RuleBasedClassifier

__all__ = [
    "BusinessFunction",
    "Classification",
    "ClassificationAgent",
    "ClassificationResult",
    "JurisdictionConfidence",
    "LLMClassifier",
    "RuleBasedClassifier",
    "TopicTag",
    "create_classification_agent",
]
