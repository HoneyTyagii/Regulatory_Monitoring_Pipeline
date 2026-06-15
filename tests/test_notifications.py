"""Tests for the notification service."""

from __future__ import annotations

from regmon.notifications import LogChannel, NotificationService, format_digest, format_single
from regmon.pipeline.context import DocumentContext, PipelineRunContext


class TestFormatting:
    def test_format_single(self, raw_document, parsed_document, risk_assessment) -> None:
        ctx = DocumentContext(
            raw=raw_document, parsed=parsed_document, risk_assessment=risk_assessment
        )
        payload = format_single(ctx)
        assert "HIGH" in payload.subject
        assert "KYC" in payload.body or "Master" in payload.body

    def test_format_digest(self, raw_document, parsed_document, risk_assessment) -> None:
        ctx = DocumentContext(
            raw=raw_document, parsed=parsed_document, risk_assessment=risk_assessment
        )
        run = PipelineRunContext(run_id="test-run", documents=[ctx])
        payload = format_digest(run)
        assert "1 document" in payload.subject
        assert "HIGH" in payload.body


class TestNotificationService:
    def test_sends_and_deduplicates(
        self, db, raw_document, parsed_document, risk_assessment
    ) -> None:
        ctx = DocumentContext(
            raw=raw_document, parsed=parsed_document, risk_assessment=risk_assessment
        )
        service = NotificationService(db, [LogChannel()])
        sent1 = service.notify_document(ctx)
        assert "log" in sent1
        sent2 = service.notify_document(ctx)
        assert sent2 == []  # dedup
