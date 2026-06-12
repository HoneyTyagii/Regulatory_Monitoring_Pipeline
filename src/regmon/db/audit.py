"""Append-only audit log.

The audit log is an immutable trail of pipeline events (documents fetched,
parsed, assessed, actions created, notifications sent, approvals granted). The
:class:`AuditLog` repository intentionally exposes only append and read
operations - there is no update or delete - so the trail stays tamper-evident
at the application layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sqlalchemy import select

from regmon.db.engine import Database
from regmon.db.records import AuditLogRecord
from regmon.logging_config import get_logger

log = get_logger(__name__)


class AuditEventType(str, Enum):
    """Well-known audit event types emitted across the pipeline."""

    DOCUMENT_FETCHED = "document.fetched"
    DOCUMENT_PARSED = "document.parsed"
    DOCUMENT_NORMALIZED = "document.normalized"
    DOCUMENT_CLASSIFIED = "document.classified"
    RISK_ASSESSED = "risk.assessed"
    ACTION_CREATED = "action.created"
    NOTIFICATION_SENT = "notification.sent"
    APPROVAL_GRANTED = "approval.granted"
    APPROVAL_REJECTED = "approval.rejected"
    ERROR = "error"


@dataclass(frozen=True)
class AuditEvent:
    """A read model for a persisted audit event."""

    id: int
    event_type: str
    entity_type: str | None
    entity_id: str | None
    actor: str
    payload: dict[str, Any]
    created_at: datetime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog:
    """Append-only repository over the ``audit_log`` table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def record(
        self,
        event_type: AuditEventType | str,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        actor: str = "system",
        payload: dict[str, Any] | None = None,
        when: datetime | None = None,
    ) -> AuditEvent:
        """Append an event to the audit log and return the persisted event."""
        event = event_type.value if isinstance(event_type, AuditEventType) else event_type
        record = AuditLogRecord(
            event_type=event,
            entity_type=entity_type,
            entity_id=entity_id,
            actor=actor,
            payload=payload or {},
            created_at=when or _utcnow(),
        )
        with self._db.session() as session:
            session.add(record)
            session.flush()
            persisted = self._to_event(record)
        log.info("audit.recorded", event_type=event, entity_id=entity_id, actor=actor)
        return persisted

    def list(
        self,
        *,
        event_type: AuditEventType | str | None = None,
        entity_id: str | None = None,
        limit: int = 100,
    ) -> list[AuditEvent]:
        """Return audit events, most recent first, optionally filtered."""
        stmt = select(AuditLogRecord).order_by(AuditLogRecord.id.desc())
        if event_type is not None:
            value = event_type.value if isinstance(event_type, AuditEventType) else event_type
            stmt = stmt.where(AuditLogRecord.event_type == value)
        if entity_id is not None:
            stmt = stmt.where(AuditLogRecord.entity_id == entity_id)
        stmt = stmt.limit(limit)
        with self._db.session() as session:
            return [self._to_event(r) for r in session.execute(stmt).scalars()]

    @staticmethod
    def _to_event(record: AuditLogRecord) -> AuditEvent:
        return AuditEvent(
            id=record.id,
            event_type=record.event_type,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            actor=record.actor,
            payload=dict(record.payload or {}),
            created_at=record.created_at,
        )


__all__ = ["AuditEvent", "AuditEventType", "AuditLog"]
