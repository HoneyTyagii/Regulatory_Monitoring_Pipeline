"""Summarization agent: produces structured summaries for parsed documents.

Operates on :class:`~regmon.models.ParsedDocument` inputs, invokes the
configured LLM for a structured summary, and optionally patches the document's
``summary`` field with the generated headline + body.
"""

from __future__ import annotations

from regmon.logging_config import get_logger
from regmon.models import ParsedDocument
from regmon.summarization.llm import LLMClient
from regmon.summarization.models import SummarizationResult

log = get_logger(__name__)


class SummarizationAgent:
    """Generates structured summaries for regulatory documents."""

    def __init__(
        self,
        llm: LLMClient,
        *,
        system_prompt: str | None = None,
    ) -> None:
        self._llm = llm
        self._system_prompt = system_prompt

    def summarize(self, parsed: ParsedDocument) -> SummarizationResult:
        """Produce a :class:`SummarizationResult` for the given document.

        The input text sent to the LLM includes the title and reference number
        as context, followed by the full clean text.
        """
        text = self._prepare_text(parsed)
        summary, usage = self._llm.summarize(text, system_prompt=self._system_prompt)
        result = SummarizationResult(
            document_id=str(parsed.id),
            summary=summary,
            model=self._llm.model_name,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
        )
        log.info(
            "summarization.completed",
            document_id=result.document_id,
            model=result.model,
            headline_len=len(summary.headline),
            key_changes=len(summary.key_changes),
            tokens=result.prompt_tokens + result.completion_tokens,
        )
        return result

    def summarize_and_patch(
        self, parsed: ParsedDocument
    ) -> tuple[ParsedDocument, SummarizationResult]:
        """Summarize and return a copy of ``parsed`` with the ``summary`` field populated."""
        result = self.summarize(parsed)
        patched = parsed.model_copy(update={"summary": result.summary.summary[:4096]})
        return patched, result

    @staticmethod
    def _prepare_text(parsed: ParsedDocument) -> str:
        parts: list[str] = []
        if parsed.title:
            parts.append(f"Title: {parsed.title}")
        if parsed.reference_number:
            parts.append(f"Reference: {parsed.reference_number}")
        if parsed.jurisdiction:
            parts.append(f"Jurisdiction: {parsed.jurisdiction.label}")
        parts.append("")
        parts.append(parsed.clean_text)
        return "\n".join(parts)


__all__ = ["SummarizationAgent"]
