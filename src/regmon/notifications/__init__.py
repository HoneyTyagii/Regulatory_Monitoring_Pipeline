"""Notification agent: Slack/email dispatch with digest formatting and dedup.

>>> from regmon.notifications import NotificationService, create_channels
>>> from regmon.config import get_settings
>>> service = NotificationService(db, create_channels(get_settings()))
>>> service.notify_document(document_context)
>>> service.notify_digest(run_context)
"""

from __future__ import annotations

from regmon.notifications.channels import (
    EmailChannel,
    LogChannel,
    NotificationChannel,
    NotificationPayload,
    SlackChannel,
    create_channels,
)
from regmon.notifications.digest import format_digest, format_single
from regmon.notifications.service import NotificationRecord, NotificationService

__all__ = [
    "EmailChannel",
    "LogChannel",
    "NotificationChannel",
    "NotificationPayload",
    "NotificationRecord",
    "NotificationService",
    "SlackChannel",
    "create_channels",
    "format_digest",
    "format_single",
]
