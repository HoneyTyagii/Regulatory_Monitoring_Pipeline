"""Source adapter for the Securities and Exchange Board of India (SEBI).

SEBI circulars and legal documents live under ``/legal/`` paths, and detail
pages are reached via ``showDetail``-style links from the listing page.
"""

from __future__ import annotations

from regmon.crawler.adapters.base import SourceAdapter
from regmon.models import Jurisdiction


class SEBIAdapter(SourceAdapter):
    """Discovers SEBI circular and legal-document detail pages."""

    jurisdiction = Jurisdiction.SEBI
    link_patterns = (
        "/legal/",
        "showdetail",
        "/sebiweb/home/detail",
        "doarchive",
    )
    same_host_only = True


__all__ = ["SEBIAdapter"]
