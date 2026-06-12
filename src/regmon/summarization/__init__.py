"""Summarization step: LLM-generated structured summaries.

>>> from regmon.summarization import SummarizationAgent, create_llm_client
>>> from regmon.config import get_settings
>>> agent = SummarizationAgent(create_llm_client(get_settings()))
>>> result = agent.summarize(parsed_document)
>>> print(result.summary.headline)
"""

from __future__ import annotations

from regmon.summarization.agent import SummarizationAgent
from regmon.summarization.llm import (
    LLMClient,
    MockLLMClient,
    OpenAILLMClient,
    create_llm_client,
)
from regmon.summarization.models import DocumentSummary, SummarizationResult

__all__ = [
    "DocumentSummary",
    "LLMClient",
    "MockLLMClient",
    "OpenAILLMClient",
    "SummarizationAgent",
    "SummarizationResult",
    "create_llm_client",
]
