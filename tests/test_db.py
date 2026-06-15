"""Tests for persistence layer and audit log."""

from __future__ import annotations

from regmon.db import AuditEventType, AuditLog, DocumentStore


class TestDocumentStore:
    def test_raw_round_trip(self, db, raw_document) -> None:
        store = DocumentStore(db)
        store.add_raw(raw_document)
        got = store.get_raw(raw_document.id)
        assert got is not None
        assert got.id == raw_document.id
        assert got.content == raw_document.content

    def test_parsed_round_trip(self, db, parsed_document) -> None:
        store = DocumentStore(db)
        store.add_parsed(parsed_document)
        got = store.get_parsed(parsed_document.id)
        assert got is not None
        assert got.title == parsed_document.title

    def test_hash_dedup(self, db, raw_document) -> None:
        store = DocumentStore(db)
        store.add_raw(raw_document)
        assert store.raw_exists_by_hash("rbi-test", raw_document.content_hash)
        assert not store.raw_exists_by_hash("rbi-test", "nonexistent")

    def test_idempotent_add(self, db, raw_document) -> None:
        store = DocumentStore(db)
        store.add_raw(raw_document)
        store.add_raw(raw_document)  # should not raise
        from regmon.models import Jurisdiction

        assert len(store.list_raw(jurisdiction=Jurisdiction.RBI)) == 1


class TestAuditLog:
    def test_record_and_list(self, db) -> None:
        audit = AuditLog(db)
        audit.record(AuditEventType.DOCUMENT_FETCHED, entity_id="doc-1", actor="test")
        audit.record(AuditEventType.DOCUMENT_PARSED, entity_id="doc-1", actor="test")
        events = audit.list()
        assert len(events) == 2

    def test_filter_by_type(self, db) -> None:
        audit = AuditLog(db)
        audit.record(AuditEventType.DOCUMENT_FETCHED, entity_id="a")
        audit.record(AuditEventType.RISK_ASSESSED, entity_id="b")
        assert len(audit.list(event_type=AuditEventType.RISK_ASSESSED)) == 1

    def test_append_only(self, db) -> None:
        audit = AuditLog(db)
        event = audit.record("custom.event", entity_id="x")
        assert event.id is not None
        assert event.created_at.tzinfo is not None
