"""LLM-backed classification agent.

Uses the configured :class:`~regmon.summarization.llm.LLMClient` to produce a
richer, context-aware classification. Falls back to the rule-based classifier
on LLM failure so the pipeline never stalls on a single document.
"""

from __future__ import annotations

import json
import re
from typing import Any

from regmon.classification.models import Classification
from regmon.classification.rules import RuleBasedClassifier
from regmon.logging_config import get_logger
from regmon.summarization.llm import LLMClient

log = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a regulatory document classifier. Given the text of a regulatory document, "
    "produce a JSON classification with these fields:\n"
    '- "topics": list of {{"topic": str, "confidence": float 0-1}}\n'
    '- "business_functions": list of {{"name": str, "relevance": float 0-1}}\n'
    '- "jurisdiction_confidence": list of {{"jurisdiction": str, "confidence": float 0-1}}\n'
    '- "document_type": one of "circular", "notification", "guideline", "regulation", '
    '"direction", "press release", or null\n'
    '- "urgency": one of "immediate", "near-term", "routine", or null\n'
    "Be precise and concise. Confidence/relevance reflects how strongly the text "
    "supports each label. Respond ONLY with valid JSON."
)


class LLMClassifier:
    """LLM-powered classifier with rule-based fallback."""

    def __init__(self, llm: LLMClient, *, fallback: RuleBasedClassifier | None = None) -> None:
        self._llm = llm
        self._fallback = fallback or RuleBasedClassifier()

    def classify(self, text: str) -> Classification:
        """Classify using the LLM, falling back to rules on error."""
        try:
            return self._llm_classify(text)
        except Exception as exc:
            log.warning("classification.llm_failed", error=str(exc))
            return self._fallback.classify(text)

    def _llm_classify(self, text: str) -> Classification:
        content = text[:50000]

        # For OpenAI-backed clients, call directly. For mock, fall back to rules.
        if hasattr(self._llm, "_api_key"):
            return self._openai_classify(content)
        return self._fallback.classify(text)

    def _openai_classify(self, text: str) -> Classification:
        """Direct OpenAI call for classification."""
        import httpx

        llm: Any = self._llm
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Classify this regulatory document:\n\n{text}"},
        ]
        response = httpx.post(
            f"{llm._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {llm._api_key}"},
            json={
                "model": llm._model,
                "messages": messages,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            },
            timeout=llm._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        return self._parse(content)

    @staticmethod
    def _parse(content: str) -> Classification:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        data = json.loads(cleaned)
        return Classification.model_validate(data)


__all__ = ["LLMClassifier"]
