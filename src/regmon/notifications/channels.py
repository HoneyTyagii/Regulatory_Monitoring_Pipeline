"""Notification channel protocol and concrete adapters (Slack, Email).

Each channel implements :meth:`send` which delivers a pre-formatted message.
Both adapters respect the ``REGMON_DRY_RUN`` flag: in dry-run mode they log
what would be sent without actually dispatching, so development/testing never
produces real notifications.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol, runtime_checkable

import httpx

from regmon.config.secrets import reveal
from regmon.config.settings import NotificationSettings, Settings
from regmon.logging_config import get_logger

log = get_logger(__name__)


@dataclass(frozen=True)
class NotificationPayload:
    """A formatted notification ready to send."""

    subject: str
    body: str
    html: str | None = None
    channel: str = "all"  # "slack", "email", or "all"


@runtime_checkable
class NotificationChannel(Protocol):
    """Protocol for outbound notification delivery."""

    @property
    def channel_name(self) -> str: ...

    def send(self, payload: NotificationPayload) -> bool:
        """Deliver the notification. Returns True on success."""
        ...


class SlackChannel:
    """Delivers notifications via a Slack incoming webhook."""

    def __init__(self, webhook_url: str, *, dry_run: bool = False, timeout: float = 10.0) -> None:
        self._webhook_url = webhook_url
        self._dry_run = dry_run
        self._timeout = timeout

    @property
    def channel_name(self) -> str:
        return "slack"

    def send(self, payload: NotificationPayload) -> bool:
        if self._dry_run:
            log.info("notify.slack.dry_run", subject=payload.subject)
            return True
        try:
            message = {"text": f"*{payload.subject}*\n\n{payload.body}"}
            response = httpx.post(
                self._webhook_url,
                json=message,
                timeout=self._timeout,
            )
            response.raise_for_status()
            log.info("notify.slack.sent", subject=payload.subject)
            return True
        except httpx.HTTPError as exc:
            log.warning("notify.slack.failed", error=str(exc))
            return False


class EmailChannel:
    """Delivers notifications via SMTP."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        username: str | None = None,
        password: str | None = None,
        from_addr: str,
        to_addrs: list[str],
        dry_run: bool = False,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from = from_addr
        self._to = to_addrs
        self._dry_run = dry_run

    @property
    def channel_name(self) -> str:
        return "email"

    def send(self, payload: NotificationPayload) -> bool:
        if self._dry_run:
            log.info("notify.email.dry_run", subject=payload.subject, to=self._to)
            return True
        try:
            msg = EmailMessage()
            msg["Subject"] = payload.subject
            msg["From"] = self._from
            msg["To"] = ", ".join(self._to)
            msg.set_content(payload.body)
            if payload.html:
                msg.add_alternative(payload.html, subtype="html")

            with smtplib.SMTP(self._host, self._port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                if self._username and self._password:
                    server.login(self._username, self._password)
                server.send_message(msg)
            log.info("notify.email.sent", subject=payload.subject, to=self._to)
            return True
        except (smtplib.SMTPException, OSError) as exc:
            log.warning("notify.email.failed", error=str(exc))
            return False


class LogChannel:
    """Mock channel that only logs (for testing and dry-run)."""

    @property
    def channel_name(self) -> str:
        return "log"

    def send(self, payload: NotificationPayload) -> bool:
        log.info("notify.log", subject=payload.subject, body_len=len(payload.body))
        return True


def create_channels(settings: Settings) -> list[NotificationChannel]:
    """Build notification channels from settings."""
    channels: list[NotificationChannel] = []
    dry_run = settings.app.dry_run
    ns: NotificationSettings = settings.notifications

    slack_url = reveal(ns.slack_webhook_url)
    if slack_url:
        channels.append(SlackChannel(slack_url, dry_run=dry_run))

    if ns.smtp_host:
        channels.append(
            EmailChannel(
                host=ns.smtp_host,
                port=ns.smtp_port,
                username=ns.smtp_username,
                password=reveal(ns.smtp_password),
                from_addr=ns.notify_from,
                to_addrs=ns.notify_to,
                dry_run=dry_run,
            )
        )

    if not channels:
        channels.append(LogChannel())

    return channels


__all__ = [
    "EmailChannel",
    "LogChannel",
    "NotificationChannel",
    "NotificationPayload",
    "SlackChannel",
    "create_channels",
]
