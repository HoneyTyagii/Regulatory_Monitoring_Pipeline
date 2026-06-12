"""Source adapter for the Reserve Bank of India (RBI).

RBI publishes notifications and press releases as HTML listing pages whose
detail links are ``*.aspx`` pages carrying an ``Id`` query parameter. The
adapter keeps anchors that look like such detail pages.
"""

from __future__ import annotations

from regmon.crawler.adapters.base import SourceAdapter
from regmon.models import Jurisdiction


class RBIAdapter(SourceAdapter):
    """Discovers RBI notification and press-release detail pages."""

    jurisdiction = Jurisdiction.RBI
    link_patterns = (
        "notificationuser.aspx",
        "pressreleasedisplay.aspx",
        "bs_circularindexdisplay.aspx",
        "notification",
        "id=",
    )
    same_host_only = True


__all__ = ["RBIAdapter"]
