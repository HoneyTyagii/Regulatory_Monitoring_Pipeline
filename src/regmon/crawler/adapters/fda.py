"""Source adapter for the U.S. Food and Drug Administration (FDA).

The FDA exposes both an RSS press-announcements feed and Federal Register
listing pages. RSS sources are parsed for item links by the base class; HTML
sources keep anchors pointing at document/news detail pages. Federal Register
documents live on a different host, so cross-host links are permitted.
"""

from __future__ import annotations

from regmon.crawler.adapters.base import SourceAdapter
from regmon.models import Jurisdiction


class FDAAdapter(SourceAdapter):
    """Discovers FDA press announcements (RSS) and Federal Register rules (HTML)."""

    jurisdiction = Jurisdiction.FDA
    link_patterns = (
        "/news-events/",
        "/drugs/",
        "/documents/",
        "/regulatory-information/",
        "federalregister.gov/documents/",
    )
    # Press-release detail pages and Federal Register documents may live on
    # different hosts than the listing page.
    same_host_only = False


__all__ = ["FDAAdapter"]
