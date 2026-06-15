"""Tests for the approval gate."""

from __future__ import annotations

from regmon.approval import ApprovalGate, ApprovalStatus
from regmon.models import RiskLevel


class TestApprovalGate:
    def test_requires_approval_for_high_risk(self, db, risk_assessment) -> None:
        gate = ApprovalGate(db)
        assert gate.requires_approval(risk_assessment) is True

    def test_auto_approves_low_risk(self, db, parsed_document) -> None:
        from regmon.models import Jurisdiction, RiskAssessment

        low = RiskAssessment(
            document_id=parsed_document.id,
            jurisdiction=Jurisdiction.RBI,
            risk_level=RiskLevel.LOW,
            score=0.1,
            rationale="Low",
        )
        from regmon.models.domain import DocumentFormat, RawDocument

        raw = RawDocument(
            source_id="s",
            jurisdiction=Jurisdiction.RBI,
            url="https://x.com",
            content="t",
            content_format=DocumentFormat.HTML,
        )
        from regmon.pipeline.context import DocumentContext

        ctx = DocumentContext(raw=raw, parsed=parsed_document, risk_assessment=low)
        gate = ApprovalGate(db)
        result = gate.auto_approve_if_eligible(ctx, "run-1")
        assert result is not None
        assert result.status == ApprovalStatus.APPROVED

    def test_approve_reject_lifecycle(self, db, parsed_document, risk_assessment) -> None:
        from regmon.models import Jurisdiction
        from regmon.models.domain import DocumentFormat, RawDocument
        from regmon.pipeline.context import DocumentContext

        raw = RawDocument(
            source_id="s",
            jurisdiction=Jurisdiction.RBI,
            url="https://x.com",
            content="t",
            content_format=DocumentFormat.HTML,
        )
        ctx = DocumentContext(
            raw=raw, parsed=parsed_document, risk_assessment=risk_assessment, action_items=[]
        )
        gate = ApprovalGate(db)
        req = gate.request_approval(ctx, "run-1")
        assert req.status == ApprovalStatus.PENDING
        assert not gate.is_approved(ctx.document_id)

        gate.approve(str(req.id), decided_by="tester")
        assert gate.is_approved(ctx.document_id)
