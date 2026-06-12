"""Classification agent: assigns topics, business functions, and jurisdiction confidence.

Operates on :class:`~regmon.models.ParsedDocument` inputs and produces a
:class:`ClassificationResult`. In mock/offline mode the rule-based classifier
runs alone; with an OpenAI key the LLM classifier takes priority with rules as
fallback.
"""

from __future__ import annotations

from regmon.classification.llm_classifier import LLMClassifier
from regmon.classification.models import Classification, ClassificationResult
from regmon.classification.rules import RuleBasedClassifier
from regmon.config.settings import Provider, Settings
from regmon.logging_config import get_logger
from regmon.models import ParsedDocument
from regmon.summarization.llm import LLMClient, create_llm_client

log = get_logger(__name__)


class ClassificationAgent:
    """Produces structured classifications for regulatory documents."""

    def __init__(
        self,
        *,
        rule_classifier: RuleBasedClassifier | None = None,
        llm_classifier: LLMClassifier | None = None,
        use_llm: bool = False,
    ) -> None:
        self._rules = rule_classifier or RuleBasedClassifier()
        self._llm = llm_classifier
        self._use_llm = use_llm and llm_classifier is not None

    def classify(self, parsed: ParsedDocument) -> ClassificationResult:
        """Classify a parsed document and return a :class:`ClassificationResult`."""
        text = parsed.clean_text
        if self._use_llm and self._llm is not None:
            classification = self._llm.classify(text)
            classifier_name = "llm"
        else:
            classification = self._rules.classify(text, declared_jurisdiction=parsed.jurisdiction)
            classifier_name = "rules"

        # Enrich with declared jurisdiction if not already present
        classification = self._ensure_jurisdiction(classification, parsed)

        log.info(
            "classification.completed",
            document_id=str(parsed.id),
            classifier=classifier_name,
            topics=len(classification.topics),
            functions=len(classification.business_functions),
            doc_type=classification.document_type,
            urgency=classification.urgency,
        )
        return ClassificationResult(
            document_id=str(parsed.id),
            classification=classification,
            classifier=classifier_name,
        )

    @staticmethod
    def _ensure_jurisdiction(
        classification: Classification, parsed: ParsedDocument
    ) -> Classification:
        """Guarantee the declared jurisdiction appears in jurisdiction_confidence."""
        declared = parsed.jurisdiction.value
        if any(j.jurisdiction == declared for j in classification.jurisdiction_confidence):
            return classification
        from regmon.classification.models import JurisdictionConfidence

        updated = [
            *classification.jurisdiction_confidence,
            JurisdictionConfidence(jurisdiction=declared, confidence=0.5),
        ]
        return classification.model_copy(update={"jurisdiction_confidence": updated})


def create_classification_agent(settings: Settings) -> ClassificationAgent:
    """Build a :class:`ClassificationAgent` from settings."""
    use_llm = settings.llm.llm_provider == Provider.OPENAI
    llm_cls: LLMClassifier | None = None
    if use_llm:
        llm_client: LLMClient = create_llm_client(settings)
        llm_cls = LLMClassifier(llm_client)
    return ClassificationAgent(use_llm=use_llm, llm_classifier=llm_cls)


__all__ = ["ClassificationAgent", "create_classification_agent"]
