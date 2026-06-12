"""SQLAlchemy ORM table definitions.

Three tables back this commit:

* ``raw_documents`` and ``parsed_documents`` form the *document store*, mirroring
  the :class:`~regmon.models.RawDocument` and
  :class:`~regmon.models.ParsedDocument` domain models.
* ``audit_log`` is an append-only event trail (see :mod:`regmon.db.audit`).

Conversions to/from the Pydantic domain models live next to each record so the
database layer stays the single place that knows the storage representation
(UUIDs as strings, enums as their values, lists/dicts as JSON).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from regmon.db.base import Base, UTCDateTime
from regmon.models import (
    DocumentFormat,
    Jurisdiction,
    ParsedDocument,
    ProcessingStatus,
    RawDocument,
)


class RawDocumentRecord(Base):
    """Persisted form of a :class:`RawDocument`."""

    __tablename__ = "raw_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    jurisdiction: Mapped[str] = mapped_column(String(32), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    content_format: Mapped[str] = mapped_column(String(16))
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict)

    @classmethod
    def from_domain(cls, doc: RawDocument) -> RawDocumentRecord:
        return cls(
            id=str(doc.id),
            source_id=doc.source_id,
            jurisdiction=doc.jurisdiction.value,
            url=str(doc.url),
            title=doc.title,
            content=doc.content,
            content_format=doc.content_format.value,
            content_hash=doc.content_hash,
            http_status=doc.http_status,
            fetched_at=doc.fetched_at,
            meta=doc.metadata,
        )

    def to_domain(self) -> RawDocument:
        return RawDocument(
            id=UUID(self.id),
            source_id=self.source_id,
            jurisdiction=Jurisdiction(self.jurisdiction),
            url=self.url,
            title=self.title,
            content=self.content,
            content_format=DocumentFormat(self.content_format),
            http_status=self.http_status,
            fetched_at=self.fetched_at,
            metadata=self.meta or {},
        )


class ParsedDocumentRecord(Base):
    """Persisted form of a :class:`ParsedDocument`."""

    __tablename__ = "parsed_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    raw_document_id: Mapped[str] = mapped_column(String(36), index=True)
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    jurisdiction: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(512))
    clean_text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_number: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    sections: Mapped[list[str]] = mapped_column(JSON, default=list)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    effective_date: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=ProcessingStatus.COMPLETED.value)
    parsed_at: Mapped[datetime] = mapped_column(UTCDateTime)

    @classmethod
    def from_domain(cls, doc: ParsedDocument) -> ParsedDocumentRecord:
        return cls(
            id=str(doc.id),
            raw_document_id=str(doc.raw_document_id),
            source_id=doc.source_id,
            jurisdiction=doc.jurisdiction.value,
            title=doc.title,
            clean_text=doc.clean_text,
            summary=doc.summary,
            reference_number=doc.reference_number,
            language=doc.language,
            keywords=doc.keywords,
            sections=doc.sections,
            published_at=doc.published_at,
            effective_date=doc.effective_date,
            status=doc.status.value,
            parsed_at=doc.parsed_at,
        )

    def to_domain(self) -> ParsedDocument:
        return ParsedDocument(
            id=UUID(self.id),
            raw_document_id=UUID(self.raw_document_id),
            source_id=self.source_id,
            jurisdiction=Jurisdiction(self.jurisdiction),
            title=self.title,
            clean_text=self.clean_text,
            summary=self.summary,
            reference_number=self.reference_number,
            language=self.language,
            keywords=list(self.keywords or []),
            sections=list(self.sections or []),
            published_at=self.published_at,
            effective_date=self.effective_date,
            status=ProcessingStatus(self.status),
            parsed_at=self.parsed_at,
        )


class AuditLogRecord(Base):
    """An append-only audit event. Never updated or deleted in normal flow."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(128), default="system")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)


__all__ = ["AuditLogRecord", "ParsedDocumentRecord", "RawDocumentRecord"]
