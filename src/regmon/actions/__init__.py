"""Action planner agent: generates concrete follow-up action items.

>>> from regmon.actions import ActionPlannerAgent
>>> planner = ActionPlannerAgent()
>>> items = planner.plan(parsed_document, risk_assessment, classification)
>>> for item in items:
...     print(item.title, item.priority.value, item.owner_team)
"""

from __future__ import annotations

from regmon.actions.planner import ActionPlannerAgent
from regmon.actions.templates import (
    ALL_TEMPLATES,
    ActionTemplate,
)

__all__ = [
    "ALL_TEMPLATES",
    "ActionPlannerAgent",
    "ActionTemplate",
]
