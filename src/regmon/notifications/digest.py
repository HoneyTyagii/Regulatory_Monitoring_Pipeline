"""Digest formatting: assembles pipeline results into human-readable notifications."""

from __future__ import annotations

from datetime import datetime, timezone

from regmon.notifications.channels import NotificationPayload
from regmon.pipeline.context import DocumentContext, PipelineRunContext


def _risk_emoji(risk_level: str) -> str:
    return {
        "critical": "\U0001f534",
        "high": "\U0001f7e0",
        "medium": "\U0001f7e1",
        "low": "\U0001f7e2",
    }.get(risk_level, "\u2753")


def format_single(ctx: DocumentContext) -> NotificationPayload:
    """Format a single processed document into a notification."""
    parsed = ctx.parsed
    assessment = ctx.risk_assessment
    if not parsed or not assessment:
        return NotificationPayload(subject="Document processed", body="No details available.")

    emoji = _risk_emoji(assessment.risk_level.value)
    subject = f"{emoji} [{assessment.risk_level.value.upper()}] {parsed.title[:80]}"

    lines: list[str] = [
        f"Document: {parsed.title}",
        f"Jurisdiction: {parsed.jurisdiction.label}",
    ]
    if parsed.reference_number:
        lines.append(f"Reference: {parsed.reference_number}")
    lines.append(f"Risk: {assessment.risk_level.value.upper()} (score: {assessment.score:.2f})")
    if parsed.summary:
        lines.append(f"\nSummary: {parsed.summary[:500]}")
    if assessment.impacted_areas:
        lines.append(f"\nImpacted areas: {', '.join(assessment.impacted_areas[:5])}")
    if ctx.action_items:
        lines.append(f"\nAction items ({len(ctx.action_items)}):")
        for i, item in enumerate(ctx.action_items[:5], 1):
            lines.append(f"  {i}. [{item.priority.value}] {item.title[:60]} -> {item.owner_team}")

    return NotificationPayload(subject=subject, body="\n".join(lines))


def format_digest(run_ctx: PipelineRunContext) -> NotificationPayload:
    """Format a full run into a digest notification."""
    processed = [d for d in run_ctx.documents if d.is_processed]
    if not processed:
        return NotificationPayload(
            subject=f"Pipeline run {run_ctx.run_id}: no new documents",
            body="All documents were duplicates or failed processing.",
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    subject = (
        f"Regulatory Digest ({now}) - {len(processed)} document(s), "
        f"{run_ctx.duplicate_count} duplicate(s)"
    )

    lines: list[str] = [
        f"Pipeline run: {run_ctx.run_id}",
        f"Processed: {len(processed)} | Duplicates: {run_ctx.duplicate_count} | Errors: {run_ctx.error_count}",
        "",
    ]

    # Group by risk level
    by_risk: dict[str, list[DocumentContext]] = {}
    for doc in processed:
        level = doc.risk_assessment.risk_level.value if doc.risk_assessment else "unknown"
        by_risk.setdefault(level, []).append(doc)

    for level in ("critical", "high", "medium", "low"):
        docs = by_risk.get(level, [])
        if not docs:
            continue
        emoji = _risk_emoji(level)
        lines.append(f"{emoji} {level.upper()} ({len(docs)}):")
        for doc in docs[:10]:
            title = doc.parsed.title[:50] if doc.parsed else "Untitled"
            ref = (
                f" [{doc.parsed.reference_number}]"
                if doc.parsed and doc.parsed.reference_number
                else ""
            )
            actions = len(doc.action_items)
            lines.append(f"  - {title}{ref} ({actions} actions)")
        lines.append("")

    return NotificationPayload(subject=subject, body="\n".join(lines))


__all__ = ["format_digest", "format_single"]
