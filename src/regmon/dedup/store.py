"""Persistent fingerprint index backed by SQLAlchemy.

Stores one fingerprint row per document so deduplication spans crawl runs. The
SimHash is stored as a 16-char hex string for dialect portability (avoiding
signed/unsigned 64-bit integer pitfalls across SQLite and PostgreSQL) and
converted back to an ``int`` for Hamming-distance scanning.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column

from regmon.db.base import Base, UTCDateTime
from regmon.db.engine import Database
from regmon.dedup.engine import Fingerprint


class DocumentFingerprintRecord(Base):
    """Persisted dedup fingerprint for a single document."""

    __tablename__ = "document_fingerprints"

    doc_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    simhash_hex: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SqlFingerprintIndex:
    """A :class:`~regmon.dedup.engine.FingerprintIndex` backed by the database."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def find_by_hash(self, content_hash: str) -> str | None:
        stmt = (
            select(DocumentFingerprintRecord.doc_id)
            .where(DocumentFingerprintRecord.content_hash == content_hash)
            .limit(1)
        )
        with self._db.session() as session:
            return session.execute(stmt).scalar_one_or_none()

    def iter_fingerprints(self) -> Iterable[Fingerprint]:
        stmt = select(DocumentFingerprintRecord)
        with self._db.session() as session:
            return [
                Fingerprint(
                    doc_id=r.doc_id,
                    content_hash=r.content_hash,
                    simhash=int(r.simhash_hex, 16),
                )
                for r in session.execute(stmt).scalars()
            ]

    def add(self, fingerprint: Fingerprint) -> None:
        record = DocumentFingerprintRecord(
            doc_id=fingerprint.doc_id,
            content_hash=fingerprint.content_hash,
            simhash_hex=f"{fingerprint.simhash:016x}",
            created_at=_utcnow(),
        )
        with self._db.session() as session:
            session.merge(record)


__all__ = ["DocumentFingerprintRecord", "SqlFingerprintIndex"]
