"""LLM client abstraction for the summarization step.

Two implementations:

* :class:`MockLLMClient` — deterministic, offline. Extracts a heuristic
  headline and returns a canned structure so the pipeline is testable without
  any network or API key.
* :class:`OpenAILLMClient` — calls the OpenAI Chat Completions API via
  ``httpx`` requesting structured JSON output that validates against the
  :class:`~regmon.summarization.models.DocumentSummary` schema.
"""

from __future__ import annotations

import json
import re
from typing import Any, Protocol, runtime_checkable

import httpx

from regmon.config.secrets import require
from regmon.config.settings import Provider, Settings
from regmon.logging_config import get_logger
from regmon.summarization.models import DocumentSummary

log = get_logger(__name__)


@runtime_checkable
class LLMClient(Protocol):
    """Protocol for LLM completions producing a structured DocumentSummary."""

    @property
    def model_name(self) -> str: ...

    def summarize(
        self, text: str, *, system_prompt: str | None = None
    ) -> tuple[DocumentSummary, dict[str, Any]]:
        """Return ``(summary, usage_dict)`` for the given document text.

        ``usage_dict`` has optional keys ``prompt_tokens`` and ``completion_tokens``.
        """
        ...


_DEFAULT_SYSTEM = (
    "You are a regulatory compliance analyst. Given the full text of a regulatory "
    "document, produce a structured JSON summary matching the provided schema. "
    "Be precise, factual, and concise. Do not invent information not present in the text."
)


class MockLLMClient:
    """Deterministic offline mock that produces a heuristic summary."""

    @property
    def model_name(self) -> str:
        return "mock"

    def summarize(
        self, text: str, *, system_prompt: str | None = None
    ) -> tuple[DocumentSummary, dict[str, Any]]:
        headline = self._extract_headline(text)
        # Strip metadata prefix lines the agent prepends
        body = text
        for prefix in ("Title:", "Reference:", "Jurisdiction:"):
            body = "\n".join(line for line in body.splitlines() if not line.startswith(prefix))
        sentences = [s.strip() for s in re.split(r"[.!?]+", body) if s.strip()]
        summary_text = ". ".join(sentences[:3]) + "." if sentences else body[:200]
        words = body.lower().split()
        tags = sorted({w for w in words if len(w) > 4 and w.isalpha()})[:5]
        doc_summary = DocumentSummary(
            headline=headline,
            summary=summary_text[:4000],
            key_changes=sentences[:3],
            affected_entities=[],
            compliance_deadline=None,
            topic_tags=tags,
        )
        return doc_summary, {"prompt_tokens": len(text.split()), "completion_tokens": 0}

    @staticmethod
    def _extract_headline(text: str) -> str:
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # Skip metadata lines
            if stripped.startswith(("Title:", "Reference:", "Jurisdiction:")):
                continue
            if len(stripped) <= 200:
                return stripped
        return text[:100].strip()


class OpenAILLMClient:
    """Calls OpenAI Chat Completions for structured JSON summarization."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        *,
        base_url: str = "https://api.openai.com/v1",
        timeout: float = 60.0,
        max_input_chars: int = 50000,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_input = max_input_chars

    @property
    def model_name(self) -> str:
        return self._model

    def summarize(
        self, text: str, *, system_prompt: str | None = None
    ) -> tuple[DocumentSummary, dict[str, Any]]:
        truncated = text[: self._max_input]
        system = system_prompt or _DEFAULT_SYSTEM
        schema = DocumentSummary.model_json_schema()
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"Summarize the following regulatory document.\n\n"
                    f"Respond ONLY with valid JSON matching this schema:\n"
                    f"```json\n{json.dumps(schema, indent=2)}\n```\n\n"
                    f"---\n\n{truncated}"
                ),
            },
        ]
        response = httpx.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "model": self._model,
                "messages": messages,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        usage = payload.get("usage", {})
        parsed = self._parse_response(content)
        return parsed, {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }

    @staticmethod
    def _parse_response(content: str) -> DocumentSummary:
        """Parse and validate the LLM's JSON output."""
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
        data = json.loads(cleaned)
        return DocumentSummary.model_validate(data)


def create_llm_client(settings: Settings) -> LLMClient:
    """Build the configured LLM client from settings."""
    if settings.llm.llm_provider == Provider.OPENAI:
        api_key = require(settings.llm.openai_api_key, "OPENAI_API_KEY")
        log.info("summarization.llm", provider="openai", model=settings.llm.openai_model)
        return OpenAILLMClient(api_key, settings.llm.openai_model)
    log.info("summarization.llm", provider="mock")
    return MockLLMClient()


__all__ = ["LLMClient", "MockLLMClient", "OpenAILLMClient", "create_llm_client"]
