"""SMTP digest transport (FR-A05). Local demos use ``RecordingNotifier``."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from uuid import uuid4

from spc_platform.application.ports.notifier import (
    DispatchReceipt,
    NotificationDigest,
)
from spc_platform.common.errors import NotificationDispatchError
from spc_platform.common.time import Clock


class SmtpNotifier:
    """Dispatch a digest as one email per recipient interval."""

    def __init__(
        self,
        clock: Clock,
        *,
        host: str,
        port: int = 25,
        sender: str = "spc-platform@local",
    ) -> None:
        self._clock = clock
        self._host = host
        self._port = port
        self._sender = sender

    def dispatch(self, digest: NotificationDigest) -> DispatchReceipt:
        """Send one email containing every digested line."""
        message = EmailMessage()
        message["Subject"] = f"SPC digest ({len(digest.items)} violation(s))"
        message["From"] = self._sender
        message["To"] = digest.recipient
        lines = [
            f"{item.severity} {item.parameter_id} {item.violation_id}"
            f" ocap={item.ocap_id or '-'} escalated={item.escalated}"
            for item in digest.items
        ]
        message.set_content("\n".join(lines))
        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as client:
                client.send_message(message)
        except OSError as exc:
            raise NotificationDispatchError(
                "SMTP dispatch failed",
                recipient=digest.recipient,
                reason=str(exc),
            ) from exc
        return DispatchReceipt(
            digest_id=f"digest-{uuid4().hex}",
            recipient=digest.recipient,
            item_count=len(digest.items),
            dispatched_at=self._clock.now(),
            transport="smtp",
        )
