"""Human-in-the-loop approval gate.

Pauses the pipeline for human review/approval before notifications are sent.
Documents above the risk threshold require explicit sign-off; lower-risk items
auto-approve.

>>> from regmon.approval import ApprovalGate
>>> gate = ApprovalGate(db)
>>> if gate.requires_approval(assessment):
...     request = gate.request_approval(doc_context, run_id)
>>> # Later, after human decision:
>>> gate.approve(str(request.id), decided_by="compliance_officer@acme.com")
"""

from __future__ import annotations

from regmon.approval.gate import DEFAULT_EXPIRY_HOURS, DEFAULT_THRESHOLD, ApprovalGate
from regmon.approval.models import ApprovalRequest, ApprovalStatus
from regmon.approval.store import ApprovalRecord, ApprovalStore

__all__ = [
    "DEFAULT_EXPIRY_HOURS",
    "DEFAULT_THRESHOLD",
    "ApprovalGate",
    "ApprovalRecord",
    "ApprovalRequest",
    "ApprovalStatus",
    "ApprovalStore",
]
