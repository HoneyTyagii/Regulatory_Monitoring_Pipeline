"""Structured output models for the summarization step."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class DocumentSummary(BaseModel):
    """LLM-generated structured summary of a regulatory document.

    Designed for downstream consumption by the risk-assessment and
    action-planner agents. All fields are populated by the LLM in a single
    structured call; the schema doubles as the system prompt instruction.
    """

    headline: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="One-sentence headline capturing the core regulatory change.",
    )
    summary: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="A 2-5 sentence plain-English summary of the document.",
    )
    key_changes: list[str] = Field(
        default_factory=list,
        description="Bullet list of specific regulatory changes or requirements.",
    )
    affected_entities: list[str] = Field(
        default_factory=list,
        description="Types of organizations or individuals affected (e.g. 'scheduled commercial banks').",
    )
    compliance_deadline: str | None = Field(
        default=None,
        max_length=128,
        description="Stated compliance deadline or effective date, if any.",
    )
    topic_tags: list[str] = Field(
        default_factory=list,
        description="Short topic keywords (e.g. 'KYC', 'capital adequacy', 'AI').",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "headline": "RBI mandates enhanced KYC for digital lending platforms",
                    "summary": "The Reserve Bank has issued updated KYC norms...",
                    "key_changes": ["New video-KYC option", "Aadhaar OTP allowed"],
                    "affected_entities": ["scheduled commercial banks", "NBFCs"],
                    "compliance_deadline": "1 April 2024",
                    "topic_tags": ["KYC", "digital lending", "identity verification"],
                }
            ]
        }
    }


@dataclass(frozen=True)
class SummarizationResult:
    """Wraps the structured summary with provenance metadata."""

    document_id: str
    summary: DocumentSummary
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = ["DocumentSummary", "SummarizationResult"]
