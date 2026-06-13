"""Approval gate data models.

Defines the lifecycle of a human approval decision: ``pending`` → ``approved``
or ``rejected``. Each approval request captures what is being approved (risk
assessment + planned actions), who is asked, and eventually who decided and why.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ApprovalStatus(str, Enum):
    """Lifecycle states of an approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    """A request for human review before notifications are sent."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=False)

    id: UUID = Field(default_factory=uuid4)
    document_id: str = Field(..., min_length=1, max_length=128)
    assessment_id: str = Field(..., min_length=1, max_length=128)
    run_id: str = Field(..., min_length=1, max_length=64)
    status: ApprovalStatus = ApprovalStatus.PENDING
    risk_level: str = Field(..., min_length=1, max_length=16)
    title: str = Field(..., min_length=1, max_length=512)
    summary: str | None = Field(default=None, max_length=4096)
    action_count: int = Field(default=0, ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)

    # Decision fields (populated on approve/reject)
    decided_by: str | None = Field(default=None, max_length=128)
    decided_at: datetime | None = None
    decision_note: str | None = Field(default=None, max_length=2048)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None


__all__ = ["ApprovalRequest", "ApprovalStatus"]
