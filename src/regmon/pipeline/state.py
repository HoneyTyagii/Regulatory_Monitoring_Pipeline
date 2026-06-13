"""Pipeline run state: long-term memory of prior runs.

Tracks which documents have been through each stage so the orchestrator can
resume from where it left off and avoid re-processing. Backed by an SQLAlchemy
table for persistence across process restarts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from regmon.db.base import Base, UTCDateTime
from regmon.db.engine import Database
from regmon.logging_config import get_logger

log = get_logger(__name__)


class PipelineStage(str, Enum):
    """Named stages in the pipeline graph."""

    FETCHED = "fetched"
    PARSED = "parsed"
    NORMALIZED = "normalized"
    DEDUPLICATED = "deduplicated"
    CLASSIFIED = "classified"
    SUMMARIZED = "summarized"
    INDEXED = "indexed"
    RISK_ASSESSED = "risk_assessed"
    ACTIONS_PLANNED = "actions_planned"
    NOTIFIED = "notified"


class PipelineStateRecord(Base):
    """Tracks the last completed stage for each document."""

    __tablename__ = "pipeline_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(String(128), index=True)
    stage: Mapped[str] = mapped_column(String(32), index=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PipelineMemory:
    """Long-term memory of pipeline progress across runs."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def mark_completed(self, document_id: str, stage: PipelineStage, run_id: str) -> None:
        """Record that a document completed a stage in a given run."""
        record = PipelineStateRecord(
            document_id=document_id,
            stage=stage.value,
            run_id=run_id,
            completed_at=_utcnow(),
        )
        with self._db.session() as session:
            session.add(record)

    def has_completed(self, document_id: str, stage: PipelineStage) -> bool:
        """Check whether a document has ever completed a stage."""
        stmt = (
            select(PipelineStateRecord.id)
            .where(
                PipelineStateRecord.document_id == document_id,
                PipelineStateRecord.stage == stage.value,
            )
            .limit(1)
        )
        with self._db.session() as session:
            return session.execute(stmt).first() is not None

    def last_run_id(self) -> str | None:
        """Return the most recent run_id, or None if no runs recorded."""
        stmt = select(PipelineStateRecord.run_id).order_by(PipelineStateRecord.id.desc()).limit(1)
        with self._db.session() as session:
            return session.execute(stmt).scalar_one_or_none()

    def documents_at_stage(self, stage: PipelineStage, run_id: str | None = None) -> list[str]:
        """Return document ids that reached a given stage, optionally in a specific run."""
        stmt = select(PipelineStateRecord.document_id).where(
            PipelineStateRecord.stage == stage.value
        )
        if run_id:
            stmt = stmt.where(PipelineStateRecord.run_id == run_id)
        with self._db.session() as session:
            return list(session.execute(stmt).scalars())


__all__ = ["PipelineMemory", "PipelineStage", "PipelineStateRecord"]
