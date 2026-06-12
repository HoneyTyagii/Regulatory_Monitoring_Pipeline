"""Source adapter for the European Union Artificial Intelligence Act.

Updates are published on the European Commission's digital-strategy site as
news items, library entries, and policy pages. The adapter keeps anchors that
point at those detail sections.
"""

from __future__ import annotations

from regmon.crawler.adapters.base import SourceAdapter
from regmon.models import Jurisdiction


class EUAIActAdapter(SourceAdapter):
    """Discovers EU AI Act news, library, and policy detail pages."""

    jurisdiction = Jurisdiction.EU_AI_ACT
    link_patterns = (
        "/news/",
        "/library/",
        "/policies/",
        "/news-redirect/",
        "artificial-intelligence",
    )
    same_host_only = True


__all__ = ["EUAIActAdapter"]
