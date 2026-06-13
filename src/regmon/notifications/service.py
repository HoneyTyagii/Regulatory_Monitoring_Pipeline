"""Notification service: dispatch with deduplication.

Tracks which document/risk-level combinations have already been notified so
repeat crawls of the same content (or re-runs after a restart) don't spam
recipients. Sent notifications are recorded in an SQLAlchemy table.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column

from regmon.db.audit import AuditEventType, AuditLog
from regmon.db.base import Base, UTCDateTime
from regmon.db.engine import Database
from regmon.logging_config import get_logger
from regmon.notifications.channels import NotificationChannel, NotificationPayload
from regmon.notifications.digest import format_digest, format_single
from regmon.pipeline.context import DocumentContext, PipelineRunContext

log = get_logger(__name__)


class NotificationRecord(Base):
    """Tracks sent notifications for dedup."""

    __tablename__ = "sent_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(128), index=True)
    risk_level: Mapped[str] = mapped_column(String(16))
    channel: Mapped[str] = mapped_column(String(32))
    subject: Mapped[str] = mapped_column(String(512))
    sent_at: Mapped[datetime] = mapped_column(UTCDateTime)


class NotificationService:
    """Dispatches notifications through configured channels with dedup."""

    def __init__(
        self,
        db: Database,
        channels: list[NotificationChannel],
        *,
        audit: AuditLog | None = None,
    ) -> None:
        self._db = db
        self._channels = channels
        self._audit = audit or AuditLog(db)

    def notify_document(self, ctx: DocumentContext) -> list[str]:
        """Send a per-document notification, skipping if already notified.

        Returns channel names that successfully delivered.
        """
        if not ctx.is_processed or ctx.risk_assessment is None:
            return []

        doc_id = ctx.document_id
        risk = ctx.risk_assessment.risk_level.value

        if self._already_sent(doc_id, risk):
            log.info("notify.dedup_skipped", document_id=doc_id, risk_level=risk)
            return []

        payload = format_single(ctx)
        sent_channels = self._dispatch(payload, ctx.document_id)

        for channel_name in sent_channels:
            self._record_sent(doc_id, risk, channel_name, payload.subject)
        if sent_channels:
            self._audit.record(
                AuditEventType.NOTIFICATION_SENT,
                entity_type="notification",
                entity_id=doc_id,
                actor="notification_agent",
                payload={"channels": sent_channels, "risk_level": risk},
            )
        return sent_channels

    def notify_digest(self, run_ctx: PipelineRunContext) -> list[str]:
        """Send a digest notification for a completed pipeline run."""
        payload = format_digest(run_ctx)
        return self._dispatch(payload, f"digest:{run_ctx.run_id}")

    def _dispatch(self, payload: NotificationPayload, ref: str) -> list[str]:
        """Send payload through all applicable channels."""
        sent: list[str] = []
        for channel in self._channels:
            if payload.channel not in ("all", channel.channel_name):
                continue
            if channel.send(payload):
                sent.append(channel.channel_name)
            else:
                log.warning("notify.channel_failed", channel=channel.channel_name, ref=ref)
        return sent

    def _already_sent(self, document_id: str, risk_level: str) -> bool:
        """Check if this document+risk combination was already notified."""
        stmt = (
            select(NotificationRecord.id)
            .where(
                NotificationRecord.document_id == document_id,
                NotificationRecord.risk_level == risk_level,
            )
            .limit(1)
        )
        with self._db.session() as session:
            return session.execute(stmt).first() is not None

    def _record_sent(self, document_id: str, risk_level: str, channel: str, subject: str) -> None:
        record = NotificationRecord(
            document_id=document_id,
            risk_level=risk_level,
            channel=channel,
            subject=subject[:512],
            sent_at=datetime.now(timezone.utc),
        )
        with self._db.session() as session:
            session.add(record)


__all__ = ["NotificationRecord", "NotificationService"]
