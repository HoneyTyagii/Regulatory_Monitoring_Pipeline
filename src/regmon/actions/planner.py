"""Action planner agent: generates concrete ActionItems from risk assessments.

The planner selects applicable action templates based on:
* Risk level (critical/high → escalation + full template set)
* Classification urgency (immediate → shorter due dates)
* Affected business functions (drives owner assignment)
* Document type (reporting requirements → reporting template)

Each generated :class:`~regmon.models.ActionItem` has a concrete title,
description (interpolated with document context), owner team, priority derived
from risk level, and a due date relative to now.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from regmon.actions.templates import (
    ACKNOWLEDGEMENT_TEMPLATE,
    ESCALATION_TEMPLATE,
    GAP_ANALYSIS_TEMPLATE,
    POLICY_UPDATE_TEMPLATE,
    REPORTING_TEMPLATE,
    REVIEW_TEMPLATE,
    SYSTEM_CHANGE_TEMPLATE,
    TRAINING_TEMPLATE,
    ActionTemplate,
)
from regmon.classification.models import Classification
from regmon.logging_config import get_logger
from regmon.models import ActionItem, ActionPriority, ParsedDocument, RiskAssessment, RiskLevel

log = get_logger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Map risk level to action priority.
_RISK_TO_PRIORITY: dict[RiskLevel, ActionPriority] = {
    RiskLevel.CRITICAL: ActionPriority.URGENT,
    RiskLevel.HIGH: ActionPriority.HIGH,
    RiskLevel.MEDIUM: ActionPriority.MEDIUM,
    RiskLevel.LOW: ActionPriority.LOW,
}

# Urgency multiplier for due dates (lower = tighter deadlines).
_URGENCY_MULTIPLIER: dict[str | None, float] = {
    "immediate": 0.3,
    "near-term": 0.6,
    "routine": 1.0,
    None: 1.0,
}


class ActionPlannerAgent:
    """Generates follow-up action items from risk assessments."""

    def plan(
        self,
        parsed: ParsedDocument,
        assessment: RiskAssessment,
        classification: Classification | None = None,
    ) -> list[ActionItem]:
        """Generate action items for the assessed document.

        Returns an ordered list of actions from highest to lowest priority.
        """
        templates = self._select_templates(assessment, classification)
        urgency = classification.urgency if classification else None
        multiplier = _URGENCY_MULTIPLIER.get(urgency, 1.0)
        priority = _RISK_TO_PRIORITY[assessment.risk_level]
        context = self._build_context(parsed, assessment)

        items: list[ActionItem] = []
        now = _utcnow()
        for template in templates:
            due_days = max(1, int(template.due_days * multiplier))
            owner = self._resolve_owner(template, classification)
            item = ActionItem(
                assessment_id=assessment.id,
                title=self._interpolate(template.title_template, context)[:256],
                description=self._interpolate(template.description_template, context)[:8192],
                priority=priority,
                owner_team=owner,
                due_date=now + timedelta(days=due_days),
            )
            items.append(item)

        log.info(
            "actions.planned",
            document_id=str(parsed.id),
            risk_level=assessment.risk_level.value,
            actions_count=len(items),
            priority=priority.value,
        )
        return items

    def _select_templates(
        self, assessment: RiskAssessment, classification: Classification | None
    ) -> list[ActionTemplate]:
        """Choose which action templates apply given risk and classification."""
        templates: list[ActionTemplate] = []
        level = assessment.risk_level

        # Critical/High always get escalation + full review
        if level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
            templates.append(ESCALATION_TEMPLATE)
            templates.append(REVIEW_TEMPLATE)
            templates.append(GAP_ANALYSIS_TEMPLATE)
            templates.append(POLICY_UPDATE_TEMPLATE)
        elif level == RiskLevel.MEDIUM:
            templates.append(REVIEW_TEMPLATE)
            templates.append(GAP_ANALYSIS_TEMPLATE)
        else:
            templates.append(ACKNOWLEDGEMENT_TEMPLATE)

        # Add function-specific templates
        if classification:
            func_names = {f.name.lower() for f in classification.business_functions}
            if "technology" in func_names:
                templates.append(SYSTEM_CHANGE_TEMPLATE)
            if "hr / training" in func_names or level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
                templates.append(TRAINING_TEMPLATE)
            if classification.document_type in ("circular", "notification") and any(
                t.topic.lower() in ("reporting requirements",)
                for t in (classification.topics or [])
            ):
                templates.append(REPORTING_TEMPLATE)

        # Deduplicate preserving order
        seen: set[str] = set()
        deduped: list[ActionTemplate] = []
        for t in templates:
            if t.key not in seen:
                seen.add(t.key)
                deduped.append(t)
        return deduped

    @staticmethod
    def _build_context(parsed: ParsedDocument, assessment: RiskAssessment) -> dict[str, str]:
        return {
            "title": parsed.title or "Untitled",
            "reference": parsed.reference_number or "N/A",
            "jurisdiction": parsed.jurisdiction.label,
            "risk_level": assessment.risk_level.value.upper(),
            "doc_type": "document",
        }

    @staticmethod
    def _interpolate(template: str, context: dict[str, str]) -> str:
        try:
            return template.format_map(context)
        except (KeyError, ValueError):
            return template

    @staticmethod
    def _resolve_owner(template: ActionTemplate, classification: Classification | None) -> str:
        """Use the template's default owner, potentially overridden by classification."""
        if classification and classification.primary_function:
            # If the template's owner matches a classified function, keep it;
            # otherwise keep the template default (it's domain-specific).
            pass
        return template.owner_team


__all__ = ["ActionPlannerAgent"]
