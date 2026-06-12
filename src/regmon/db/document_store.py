"""Document store: persistence for raw and parsed documents.

Provides a small repository over the ``raw_documents`` and ``parsed_documents``
tables, translating to and from the Pydantic domain models. Writes are
idempotent on primary key (via ``merge``), so re-persisting a document with the
same id updates it in place rather than failing.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from regmon.db.engine import Database
from regmon.db.records import ParsedDocumentRecord, RawDocumentRecord
from regmon.logging_config import get_logger
from regmon.models import Jurisdiction, ParsedDocument, RawDocument

log = get_logger(__name__)


class DocumentStore:
    """Stores and retrieves raw and parsed documents."""

    def __init__(self, db: Database) -> None:
        self._db = db

    # -- raw documents ------------------------------------------------------

    def add_raw(self, doc: RawDocument) -> RawDocument:
        """Persist a raw document (idempotent on id) and return it."""
        with self._db.session() as session:
            session.merge(RawDocumentRecord.from_domain(doc))
        log.info("db.raw_stored", id=str(doc.id), source_id=doc.source_id)
        return doc

    def get_raw(self, doc_id: UUID | str) -> RawDocument | None:
        """Return a raw document by id, or ``None`` if absent."""
        with self._db.session() as session:
            record = session.get(RawDocumentRecord, str(doc_id))
            return record.to_domain() if record is not None else None

    def raw_exists_by_hash(self, source_id: str, content_hash: str) -> bool:
        """Return whether a raw document with this content hash exists for a source."""
        stmt = select(RawDocumentRecord.id).where(
            RawDocumentRecord.source_id == source_id,
            RawDocumentRecord.content_hash == content_hash,
        )
        with self._db.session() as session:
            return session.execute(stmt).first() is not None

    def list_raw(
        self, *, jurisdiction: Jurisdiction | None = None, limit: int = 100
    ) -> list[RawDocument]:
        """List raw documents, most recently fetched first."""
        stmt = select(RawDocumentRecord).order_by(RawDocumentRecord.fetched_at.desc())
        if jurisdiction is not None:
            stmt = stmt.where(RawDocumentRecord.jurisdiction == jurisdiction.value)
        stmt = stmt.limit(limit)
        with self._db.session() as session:
            return [r.to_domain() for r in session.execute(stmt).scalars()]

    # -- parsed documents ---------------------------------------------------

    def add_parsed(self, doc: ParsedDocument) -> ParsedDocument:
        """Persist a parsed document (idempotent on id) and return it."""
        with self._db.session() as session:
            session.merge(ParsedDocumentRecord.from_domain(doc))
        log.info("db.parsed_stored", id=str(doc.id), source_id=doc.source_id)
        return doc

    def get_parsed(self, doc_id: UUID | str) -> ParsedDocument | None:
        """Return a parsed document by id, or ``None`` if absent."""
        with self._db.session() as session:
            record = session.get(ParsedDocumentRecord, str(doc_id))
            return record.to_domain() if record is not None else None

    def list_parsed(
        self, *, jurisdiction: Jurisdiction | None = None, limit: int = 100
    ) -> list[ParsedDocument]:
        """List parsed documents, most recently parsed first."""
        stmt = select(ParsedDocumentRecord).order_by(ParsedDocumentRecord.parsed_at.desc())
        if jurisdiction is not None:
            stmt = stmt.where(ParsedDocumentRecord.jurisdiction == jurisdiction.value)
        stmt = stmt.limit(limit)
        with self._db.session() as session:
            return [r.to_domain() for r in session.execute(stmt).scalars()]


__all__ = ["DocumentStore"]
