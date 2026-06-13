"""Rule-based risk scoring engine.

Computes a normalized risk score in ``[0.0, 1.0]`` from document signals:

* Urgency (classification output) — immediate/near-term/routine.
* Document type — circulars/regulations score higher than press releases.
* Keywords — penalty, enforcement, prohibition, revocation, etc.
* Impacted scope — how many business functions are affected.
* Jurisdiction novelty signals (new regulation vs. amendment).

Individual signal scores are weighted and capped to produce the final composite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from regmon.classification.models import Classification

# -- signal weights ---------------------------------------------------------

_W_URGENCY = 0.25
_W_DOC_TYPE = 0.15
_W_KEYWORDS = 0.30
_W_SCOPE = 0.15
_W_PENALTY = 0.15

# -- urgency ----------------------------------------------------------------

_URGENCY_SCORES: dict[str | None, float] = {
    "immediate": 1.0,
    "near-term": 0.6,
    "routine": 0.2,
    None: 0.3,
}

# -- document type ----------------------------------------------------------

_DOC_TYPE_SCORES: dict[str | None, float] = {
    "regulation": 0.9,
    "direction": 0.85,
    "circular": 0.7,
    "notification": 0.6,
    "guideline": 0.5,
    "press release": 0.2,
    None: 0.4,
}

# -- high-risk keywords (presence scores) -----------------------------------

_HIGH_RISK_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    (re.compile(r"\bpenalt(?:y|ies)\b", re.IGNORECASE), 0.8),
    (re.compile(r"\benforcemen[t]\b", re.IGNORECASE), 0.7),
    (re.compile(r"\bprohibit(?:ed|ion)?\b", re.IGNORECASE), 0.9),
    (re.compile(r"\brevok(?:e|ed|ation)\b", re.IGNORECASE), 0.9),
    (re.compile(r"\bsuspend(?:ed|sion)?\b", re.IGNORECASE), 0.8),
    (re.compile(r"\bmandatory\b", re.IGNORECASE), 0.6),
    (re.compile(r"\bwith immediate effect\b", re.IGNORECASE), 0.9),
    (re.compile(r"\bnon-?compliance\b", re.IGNORECASE), 0.7),
    (re.compile(r"\bbreach\b", re.IGNORECASE), 0.6),
    (re.compile(r"\bcessation\b", re.IGNORECASE), 0.8),
    (re.compile(r"\bsupersede[sd]?\b", re.IGNORECASE), 0.5),
]

# -- penalty amount detector ------------------------------------------------

_AMOUNT_RE = re.compile(
    r"(?:Rs\.?|INR|USD|\$|€|EUR)\s*[\d,]+(?:\.\d+)?(?:\s*(?:crore|lakh|million|billion))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RiskSignals:
    """Individual signal scores before weighting."""

    urgency: float
    doc_type: float
    keywords: float
    scope: float
    penalty: float
    composite: float


def compute_risk_score(
    text: str,
    classification: Classification | None = None,
) -> tuple[float, RiskSignals, list[str]]:
    """Compute a composite risk score, constituent signals, and impacted areas.

    Returns ``(score, signals, impacted_areas)`` where score is in [0.0, 1.0].
    """
    urgency_val = _URGENCY_SCORES.get(classification.urgency if classification else None, 0.3)
    doc_type_val = _DOC_TYPE_SCORES.get(
        classification.document_type if classification else None, 0.4
    )
    keywords_val = _score_keywords(text)
    scope_val = _score_scope(classification)
    penalty_val = min(len(_AMOUNT_RE.findall(text)) * 0.4, 1.0)

    composite = (
        urgency_val * _W_URGENCY
        + doc_type_val * _W_DOC_TYPE
        + keywords_val * _W_KEYWORDS
        + scope_val * _W_SCOPE
        + penalty_val * _W_PENALTY
    )
    composite = round(min(max(composite, 0.0), 1.0), 4)

    impacted = _impacted_areas(classification)
    signals = RiskSignals(
        urgency=urgency_val,
        doc_type=doc_type_val,
        keywords=keywords_val,
        scope=scope_val,
        penalty=penalty_val,
        composite=composite,
    )
    return composite, signals, impacted


def _score_keywords(text: str) -> float:
    matched = [weight for pattern, weight in _HIGH_RISK_PATTERNS if pattern.search(text)]
    if not matched:
        return 0.0
    return min(sum(matched) / len(_HIGH_RISK_PATTERNS), 1.0)


def _score_scope(classification: Classification | None) -> float:
    if classification is None:
        return 0.3
    n_funcs = len(classification.business_functions)
    return min(n_funcs / 4.0, 1.0)


def _impacted_areas(classification: Classification | None) -> list[str]:
    if classification is None:
        return []
    return [f.name for f in classification.business_functions]


__all__ = ["RiskSignals", "compute_risk_score"]
