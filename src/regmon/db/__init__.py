"""Persistence layer: SQLAlchemy engine, document store, and audit log.

>>> from regmon.db import create_database, DocumentStore, AuditLog
>>> db = create_database("sqlite:///./data/regmon.sqlite")
>>> db.create_all()
>>> store = DocumentStore(db)
>>> audit = AuditLog(db)
"""

from __future__ import annotations

from regmon.db.audit import AuditEvent, AuditEventType, AuditLog
from regmon.db.base import Base, UTCDateTime
from regmon.db.document_store import DocumentStore
from regmon.db.engine import Database, create_database
from regmon.db.records import (
    AuditLogRecord,
    ParsedDocumentRecord,
    RawDocumentRecord,
)

__all__ = [
    "AuditEvent",
    "AuditEventType",
    "AuditLog",
    "AuditLogRecord",
    "Base",
    "Database",
    "DocumentStore",
    "ParsedDocumentRecord",
    "RawDocumentRecord",
    "UTCDateTime",
    "create_database",
]
