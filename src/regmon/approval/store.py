"""SQLAlchemy persistence for approval requests."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from regmon.approval.models import ApprovalRequest, ApprovalStatus
from regmon.db.base import Base, UTCDateTime
from regmon.db.engine import Database


class ApprovalRecord(Base):
    """Persisted approval request."""

    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(String(128), index=True)
    assessment_id: Mapped[str] = mapped_column(String(128), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    risk_level: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(512))
    summary: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    action_count: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    decided_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    decision_note: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    @classmethod
    def from_domain(cls, req: ApprovalRequest) -> ApprovalRecord:
        return cls(
            id=str(req.id),
            document_id=req.document_id,
            assessment_id=req.assessment_id,
            run_id=req.run_id,
            status=req.status.value,
            risk_level=req.risk_level,
            title=req.title,
            summary=req.summary,
            action_count=req.action_count,
            payload=req.payload,
            decided_by=req.decided_by,
            decided_at=req.decided_at,
            decision_note=req.decision_note,
            created_at=req.created_at,
            expires_at=req.expires_at,
        )

    def to_domain(self) -> ApprovalRequest:
        return ApprovalRequest(
            id=UUID(self.id),
            document_id=self.document_id,
            assessment_id=self.assessment_id,
            run_id=self.run_id,
            status=ApprovalStatus(self.status),
            risk_level=self.risk_level,
            title=self.title,
            summary=self.summary,
            action_count=self.action_count,
            payload=self.payload or {},
            decided_by=self.decided_by,
            decided_at=self.decided_at,
            decision_note=self.decision_note,
            created_at=self.created_at,
            expires_at=self.expires_at,
        )


class ApprovalStore:
    """Repository for approval requests."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def create(self, request: ApprovalRequest) -> ApprovalRequest:
        """Persist a new approval request."""
        with self._db.session() as session:
            session.add(ApprovalRecord.from_domain(request))
        return request

    def get(self, approval_id: UUID | str) -> ApprovalRequest | None:
        """Retrieve an approval by id."""
        with self._db.session() as session:
            record = session.get(ApprovalRecord, str(approval_id))
            return record.to_domain() if record else None

    def update_decision(
        self,
        approval_id: UUID | str,
        status: ApprovalStatus,
        decided_by: str,
        *,
        note: str | None = None,
        decided_at: datetime | None = None,
    ) -> ApprovalRequest | None:
        """Record a decision (approve/reject) on a pending request."""
        from datetime import timezone

        with self._db.session() as session:
            record = session.get(ApprovalRecord, str(approval_id))
            if record is None:
                return None
            record.status = status.value
            record.decided_by = decided_by
            record.decided_at = decided_at or datetime.now(timezone.utc)
            record.decision_note = note
        return self.get(approval_id)

    def list_pending(self, *, run_id: str | None = None) -> list[ApprovalRequest]:
        """Return all pending approval requests, optionally for a specific run."""
        stmt = select(ApprovalRecord).where(ApprovalRecord.status == ApprovalStatus.PENDING.value)
        if run_id:
            stmt = stmt.where(ApprovalRecord.run_id == run_id)
        stmt = stmt.order_by(ApprovalRecord.created_at.desc())
        with self._db.session() as session:
            return [r.to_domain() for r in session.execute(stmt).scalars()]

    def list_by_document(self, document_id: str) -> list[ApprovalRequest]:
        """Return all approvals for a document, newest first."""
        stmt = (
            select(ApprovalRecord)
            .where(ApprovalRecord.document_id == document_id)
            .order_by(ApprovalRecord.created_at.desc())
        )
        with self._db.session() as session:
            return [r.to_domain() for r in session.execute(stmt).scalars()]


__all__ = ["ApprovalRecord", "ApprovalStore"]
