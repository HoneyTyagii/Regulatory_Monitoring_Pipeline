"""Rule-based classifier using keyword matching.

Provides deterministic, explainable classification with no LLM dependency.
Each topic and business-function rule is a set of trigger keywords; confidence
is proportional to how many keywords matched relative to the rule's total.
This is the offline default and also serves as a fast first-pass for filtering
before an optional LLM re-classification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from regmon.classification.models import (
    BusinessFunction,
    Classification,
    JurisdictionConfidence,
    TopicTag,
)
from regmon.models import Jurisdiction

# -- topic rules ------------------------------------------------------------


@dataclass(frozen=True)
class _TopicRule:
    topic: str
    keywords: frozenset[str]
    min_matches: int = 1


_TOPIC_RULES: list[_TopicRule] = [
    _TopicRule(
        "capital adequacy", frozenset(["capital", "adequacy", "basel", "car", "crar", "tier"])
    ),
    _TopicRule(
        "KYC / AML",
        frozenset(
            ["kyc", "aml", "anti-money", "laundering", "customer due diligence", "cdd", "identity"]
        ),
    ),
    _TopicRule(
        "digital lending",
        frozenset(["digital lending", "fintech", "nbfc", "lending platform", "rbi digital"]),
    ),
    _TopicRule(
        "data privacy", frozenset(["data protection", "privacy", "gdpr", "personal data", "dpdp"])
    ),
    _TopicRule(
        "AI regulation",
        frozenset(
            ["artificial intelligence", "ai act", "ai system", "algorithmic", "machine learning"]
        ),
    ),
    _TopicRule(
        "securities disclosure",
        frozenset(["disclosure", "mutual fund", "portfolio", "sebi circular", "insider trading"]),
    ),
    _TopicRule(
        "clinical trials",
        frozenset(["clinical trial", "fda approval", "21 cfr", "medical device", "drug safety"]),
    ),
    _TopicRule(
        "payments",
        frozenset(["upi", "payment system", "rtgs", "neft", "payment aggregator", "ppi"]),
    ),
    _TopicRule(
        "cybersecurity",
        frozenset(
            ["cyber", "information security", "incident reporting", "it governance", "ransomware"]
        ),
    ),
    _TopicRule(
        "consumer protection",
        frozenset(["consumer", "grievance", "ombudsman", "fair practice", "complaint"]),
    ),
    _TopicRule(
        "licensing", frozenset(["license", "licence", "authorization", "registration", "permit"])
    ),
    _TopicRule(
        "reporting requirements",
        frozenset(["reporting", "return", "filing", "disclosure", "submission"]),
    ),
]

# -- business function rules ------------------------------------------------


@dataclass(frozen=True)
class _FunctionRule:
    name: str
    keywords: frozenset[str]


_FUNCTION_RULES: list[_FunctionRule] = [
    _FunctionRule(
        "Compliance", frozenset(["compliance", "regulatory", "circular", "notification", "mandate"])
    ),
    _FunctionRule(
        "Risk Management", frozenset(["risk", "exposure", "capital", "stress test", "provisioning"])
    ),
    _FunctionRule(
        "Legal", frozenset(["act", "section", "regulation", "statute", "penalty", "enforcement"])
    ),
    _FunctionRule(
        "Operations", frozenset(["process", "procedure", "operational", "implementation", "system"])
    ),
    _FunctionRule(
        "Technology", frozenset(["technology", "digital", "cyber", "software", "platform", "api"])
    ),
    _FunctionRule(
        "Finance",
        frozenset(["accounting", "audit", "financial statement", "disclosure", "reporting"]),
    ),
    _FunctionRule("Product", frozenset(["product", "scheme", "offering", "service", "customer"])),
    _FunctionRule(
        "HR / Training", frozenset(["training", "employee", "staff", "human resource", "awareness"])
    ),
]

# -- jurisdiction detection -------------------------------------------------

_JURISDICTION_KEYWORDS: dict[Jurisdiction, frozenset[str]] = {
    Jurisdiction.RBI: frozenset(
        ["rbi", "reserve bank", "banking regulation act", "nbfc", "scheduled commercial bank"]
    ),
    Jurisdiction.SEBI: frozenset(
        ["sebi", "securities and exchange board", "mutual fund", "stock exchange", "listing"]
    ),
    Jurisdiction.FDA: frozenset(
        ["fda", "food and drug", "21 cfr", "federal register", "clinical trial"]
    ),
    Jurisdiction.EU_AI_ACT: frozenset(
        ["eu ai act", "artificial intelligence act", "european commission", "annex", "high-risk ai"]
    ),
}

# -- document type detection ------------------------------------------------

_DOC_TYPE_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("circular", re.compile(r"\bcircular\b", re.IGNORECASE)),
    ("notification", re.compile(r"\bnotification\b", re.IGNORECASE)),
    ("guideline", re.compile(r"\bguideline\b", re.IGNORECASE)),
    ("regulation", re.compile(r"\bregulation\b", re.IGNORECASE)),
    ("direction", re.compile(r"\bdirection\b", re.IGNORECASE)),
    ("press release", re.compile(r"\bpress release\b", re.IGNORECASE)),
]

# -- urgency detection -------------------------------------------------------

_URGENCY_IMMEDIATE = re.compile(
    r"\b(immediate(?:ly)?|with immediate effect|forthwith|urgent)\b", re.IGNORECASE
)
_URGENCY_NEAR = re.compile(
    r"\b(within \d+ days|by \w+ \d{4}|effective from|deadline)\b", re.IGNORECASE
)


def _count_matches(text_lower: str, keywords: frozenset[str]) -> int:
    return sum(1 for kw in keywords if kw in text_lower)


class RuleBasedClassifier:
    """Keyword-based classifier producing deterministic classifications."""

    def classify(
        self, text: str, *, declared_jurisdiction: Jurisdiction | None = None
    ) -> Classification:
        """Classify the document text and return a :class:`Classification`."""
        text_lower = text.lower()
        topics = self._classify_topics(text_lower)
        functions = self._classify_functions(text_lower)
        jurisdictions = self._classify_jurisdictions(text_lower, declared_jurisdiction)
        doc_type = self._detect_type(text_lower)
        urgency = self._detect_urgency(text_lower)
        return Classification(
            topics=topics,
            business_functions=functions,
            jurisdiction_confidence=jurisdictions,
            document_type=doc_type,
            urgency=urgency,
        )

    def _classify_topics(self, text_lower: str) -> list[TopicTag]:
        tags: list[TopicTag] = []
        for rule in _TOPIC_RULES:
            matches = _count_matches(text_lower, rule.keywords)
            if matches >= rule.min_matches:
                confidence = min(matches / max(len(rule.keywords) * 0.5, 1), 1.0)
                tags.append(TopicTag(topic=rule.topic, confidence=round(confidence, 3)))
        return sorted(tags, key=lambda t: t.confidence, reverse=True)

    def _classify_functions(self, text_lower: str) -> list[BusinessFunction]:
        funcs: list[BusinessFunction] = []
        for rule in _FUNCTION_RULES:
            matches = _count_matches(text_lower, rule.keywords)
            if matches >= 1:
                relevance = min(matches / max(len(rule.keywords) * 0.4, 1), 1.0)
                funcs.append(BusinessFunction(name=rule.name, relevance=round(relevance, 3)))
        return sorted(funcs, key=lambda f: f.relevance, reverse=True)

    def _classify_jurisdictions(
        self, text_lower: str, declared: Jurisdiction | None
    ) -> list[JurisdictionConfidence]:
        results: list[JurisdictionConfidence] = []
        for jur, keywords in _JURISDICTION_KEYWORDS.items():
            matches = _count_matches(text_lower, keywords)
            if matches > 0:
                confidence = min(matches / max(len(keywords) * 0.4, 1), 1.0)
                if jur == declared:
                    confidence = min(confidence + 0.2, 1.0)
                results.append(
                    JurisdictionConfidence(jurisdiction=jur.value, confidence=round(confidence, 3))
                )
        if declared and not any(r.jurisdiction == declared.value for r in results):
            results.append(JurisdictionConfidence(jurisdiction=declared.value, confidence=0.5))
        return sorted(results, key=lambda j: j.confidence, reverse=True)

    @staticmethod
    def _detect_type(text_lower: str) -> str | None:
        for doc_type, pattern in _DOC_TYPE_PATTERNS:
            if pattern.search(text_lower):
                return doc_type
        return None

    @staticmethod
    def _detect_urgency(text_lower: str) -> str | None:
        if _URGENCY_IMMEDIATE.search(text_lower):
            return "immediate"
        if _URGENCY_NEAR.search(text_lower):
            return "near-term"
        return "routine"


__all__ = ["RuleBasedClassifier"]
