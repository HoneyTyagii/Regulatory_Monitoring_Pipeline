"""Action templates: predefined follow-up actions keyed by topic and function.

Each template describes a concrete compliance task that should be created when
a document matches certain conditions. Templates provide defaults for title,
description, owner team, and relative due-date (days from now); the planner
personalizes them with document-specific context at generation time.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionTemplate:
    """A reusable action blueprint."""

    key: str
    title_template: str
    description_template: str
    owner_team: str
    due_days: int


# -- generic actions by urgency/risk ----------------------------------------

REVIEW_TEMPLATE = ActionTemplate(
    key="review",
    title_template="Review {doc_type}: {title}",
    description_template=(
        "Review the regulatory document '{title}' ({reference}) from {jurisdiction}. "
        "Assess applicability to current operations and identify required changes."
    ),
    owner_team="Compliance",
    due_days=14,
)

GAP_ANALYSIS_TEMPLATE = ActionTemplate(
    key="gap_analysis",
    title_template="Conduct gap analysis for {title}",
    description_template=(
        "Perform a gap analysis between current policies/processes and the requirements "
        "of '{title}' ({reference}). Document gaps and remediation steps."
    ),
    owner_team="Compliance",
    due_days=21,
)

POLICY_UPDATE_TEMPLATE = ActionTemplate(
    key="policy_update",
    title_template="Update policies per {reference}",
    description_template=(
        "Update internal policies and procedures to comply with {title} ({reference}). "
        "Coordinate with Legal and affected business units."
    ),
    owner_team="Legal",
    due_days=30,
)

SYSTEM_CHANGE_TEMPLATE = ActionTemplate(
    key="system_change",
    title_template="Implement system changes for {reference}",
    description_template=(
        "Implement required system/technology changes to comply with '{title}' ({reference}). "
        "Coordinate with Technology and Operations teams."
    ),
    owner_team="Technology",
    due_days=45,
)

TRAINING_TEMPLATE = ActionTemplate(
    key="training",
    title_template="Conduct training on {title}",
    description_template=(
        "Develop and deliver training materials covering the requirements of '{title}' "
        "({reference}) to affected staff and stakeholders."
    ),
    owner_team="HR / Training",
    due_days=30,
)

REPORTING_TEMPLATE = ActionTemplate(
    key="reporting",
    title_template="Set up regulatory reporting for {reference}",
    description_template=(
        "Configure reporting processes and systems to meet the filing requirements "
        "of '{title}' ({reference}) within the stated deadline."
    ),
    owner_team="Finance",
    due_days=21,
)

ESCALATION_TEMPLATE = ActionTemplate(
    key="escalation",
    title_template="Escalate to senior management: {title}",
    description_template=(
        "Escalate '{title}' ({reference}) to senior management for decision. "
        "Risk level: {risk_level}. Immediate attention required."
    ),
    owner_team="Risk Management",
    due_days=3,
)

ACKNOWLEDGEMENT_TEMPLATE = ActionTemplate(
    key="acknowledgement",
    title_template="Acknowledge receipt of {reference}",
    description_template=(
        "File acknowledgement of regulatory communication '{title}' ({reference}) "
        "and log in the compliance register."
    ),
    owner_team="Compliance",
    due_days=7,
)


# -- ordered by priority for selection logic --------------------------------

ALL_TEMPLATES: list[ActionTemplate] = [
    ESCALATION_TEMPLATE,
    REVIEW_TEMPLATE,
    GAP_ANALYSIS_TEMPLATE,
    POLICY_UPDATE_TEMPLATE,
    SYSTEM_CHANGE_TEMPLATE,
    TRAINING_TEMPLATE,
    REPORTING_TEMPLATE,
    ACKNOWLEDGEMENT_TEMPLATE,
]

__all__ = [
    "ACKNOWLEDGEMENT_TEMPLATE",
    "ALL_TEMPLATES",
    "ESCALATION_TEMPLATE",
    "GAP_ANALYSIS_TEMPLATE",
    "POLICY_UPDATE_TEMPLATE",
    "REPORTING_TEMPLATE",
    "REVIEW_TEMPLATE",
    "SYSTEM_CHANGE_TEMPLATE",
    "TRAINING_TEMPLATE",
    "ActionTemplate",
]
