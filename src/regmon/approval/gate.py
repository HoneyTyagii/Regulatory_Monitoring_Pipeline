"""Approval gate: pause pipeline for human review before notifications.

The gate is consulted after action planning and before notification dispatch.
Documents at or above a configurable risk threshold require explicit approval;
lower-risk items auto-approve so low-noise docs flow without friction.

Decisions are persisted so the audit trail shows who approved/rejected what and
when, and so the pipeline can resume after a decision is made (even across
process restarts).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from regmon.approval.models import ApprovalRequest, ApprovalStatus
from regmon.approval.store import ApprovalStore
from regmon.db.audit import AuditEventType, AuditLog
from regmon.db.engine import Database
from regmon.logging_config import get_logger
from regmon.models import RiskAssessment, RiskLevel
from regmon.pipeline.context import DocumentContext

log = get_logger(__name__)

#: Default: HIGH and CRITICAL require human approval.
DEFAULT_THRESHOLD = RiskLevel.HIGH

#: How long an approval request stays valid before expiring.
DEFAULT_EXPIRY_HOURS = 72


class ApprovalGate:
    """Creates and resolves human-in-the-loop approval requests."""

    def __init__(
        self,
        db: Database,
        *,
        store: ApprovalStore | None = None,
        audit: AuditLog | None = None,
        threshold: RiskLevel = DEFAULT_THRESHOLD,
        expiry_hours: int = DEFAULT_EXPIRY_HOURS,
        auto_approve_below_threshold: bool = True,
    ) -> None:
        self._store = store or ApprovalStore(db)
        self._audit = audit or AuditLog(db)
        self._threshold = threshold
        self._expiry_hours = expiry_hours
        self._auto_approve = auto_approve_below_threshold

    def requires_approval(self, assessment: RiskAssessment) -> bool:
        """Return whether this assessment's risk level requires human sign-off."""
        return assessment.risk_level.severity >= self._threshold.severity

    def request_approval(self, ctx: DocumentContext, run_id: str) -> ApprovalRequest:
        """Create a pending approval request for the document context.

        The request captures the risk assessment, planned actions, and summary
        so the reviewer has full context without navigating multiple systems.
        """
        assessment = ctx.risk_assessment
        parsed = ctx.parsed
        if assessment is None or parsed is None:
            raise ValueError("cannot request approval without risk assessment and parsed document")

        now = datetime.now(timezone.utc)
        request = ApprovalRequest(
            document_id=ctx.document_id,
            assessment_id=str(assessment.id),
            run_id=run_id,
            risk_level=assessment.risk_level.value,
            title=parsed.title,
            summary=parsed.summary,
            action_count=len(ctx.action_items),
            payload={
                "score": assessment.score,
                "rationale": assessment.rationale[:2000],
                "impacted_areas": assessment.impacted_areas,
                "actions": [
                    {"title": a.title, "priority": a.priority.value, "owner": a.owner_team}
                    for a in ctx.action_items[:10]
                ],
            },
            expires_at=now + timedelta(hours=self._expiry_hours),
        )
        self._store.create(request)
        self._audit.record(
            "approval.requested",
            entity_type="approval",
            entity_id=str(request.id),
            actor="pipeline",
            payload={"risk_level": request.risk_level, "document_id": request.document_id},
        )
        log.info(
            "approval.requested",
            document_id=ctx.document_id,
            risk_level=request.risk_level,
            approval_id=str(request.id),
        )
        return request

    def auto_approve_if_eligible(self, ctx: DocumentContext, run_id: str) -> ApprovalRequest | None:
        """Auto-approve documents below the threshold, returning the request or None.

        Returns ``None`` if the document requires manual approval.
        """
        assessment = ctx.risk_assessment
        if assessment is None:
            return None
        if self.requires_approval(assessment):
            return None
        if not self._auto_approve:
            return None

        parsed = ctx.parsed
        request = ApprovalRequest(
            document_id=ctx.document_id,
            assessment_id=str(assessment.id),
            run_id=run_id,
            status=ApprovalStatus.APPROVED,
            risk_level=assessment.risk_level.value,
            title=parsed.title if parsed else "Untitled",
            action_count=len(ctx.action_items),
            decided_by="auto",
            decided_at=datetime.now(timezone.utc),
            decision_note="Auto-approved: risk below threshold",
        )
        self._store.create(request)
        self._audit.record(
            AuditEventType.APPROVAL_GRANTED,
            entity_type="approval",
            entity_id=str(request.id),
            actor="auto",
            payload={"risk_level": request.risk_level},
        )
        log.info("approval.auto_approved", document_id=ctx.document_id)
        return request

    def approve(
        self, approval_id: str, *, decided_by: str, note: str | None = None
    ) -> ApprovalRequest | None:
        """Record an approval decision."""
        result = self._store.update_decision(
            approval_id, ApprovalStatus.APPROVED, decided_by, note=note
        )
        if result:
            self._audit.record(
                AuditEventType.APPROVAL_GRANTED,
                entity_type="approval",
                entity_id=approval_id,
                actor=decided_by,
                payload={"note": note},
            )
            log.info("approval.approved", approval_id=approval_id, by=decided_by)
        return result

    def reject(
        self, approval_id: str, *, decided_by: str, note: str | None = None
    ) -> ApprovalRequest | None:
        """Record a rejection decision."""
        result = self._store.update_decision(
            approval_id, ApprovalStatus.REJECTED, decided_by, note=note
        )
        if result:
            self._audit.record(
                AuditEventType.APPROVAL_REJECTED,
                entity_type="approval",
                entity_id=approval_id,
                actor=decided_by,
                payload={"note": note},
            )
            log.info("approval.rejected", approval_id=approval_id, by=decided_by)
        return result

    def get_pending(self, run_id: str | None = None) -> list[ApprovalRequest]:
        """Return all pending approval requests."""
        return self._store.list_pending(run_id=run_id)

    def is_approved(self, document_id: str) -> bool:
        """Check whether a document has been approved (any request)."""
        approvals = self._store.list_by_document(document_id)
        return any(a.status == ApprovalStatus.APPROVED for a in approvals)


__all__ = ["DEFAULT_EXPIRY_HOURS", "DEFAULT_THRESHOLD", "ApprovalGate"]
