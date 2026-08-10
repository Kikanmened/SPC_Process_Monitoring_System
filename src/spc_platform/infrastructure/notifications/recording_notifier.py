"""In-memory notifier for local demos and tests (FR-A05)."""

from __future__ import annotations

from uuid import uuid4

from spc_platform.application.ports.notifier import (
    DispatchReceipt,
    NotificationDigest,
)
from spc_platform.common.errors import NotificationDispatchError
from spc_platform.common.time import Clock


class RecordingNotifier:
    """Records digests without contacting an external transport."""

    def __init__(self, clock: Clock, *, fail: bool = False) -> None:
        self._clock = clock
        self._fail = fail
        self.dispatched: list[NotificationDigest] = []

    def dispatch(self, digest: NotificationDigest) -> DispatchReceipt:
        """Append the digest or raise when configured to fail."""
        if self._fail:
            raise NotificationDispatchError(
                "notification transport refused the digest",
                recipient=digest.recipient,
            )
        self.dispatched.append(digest)
        return DispatchReceipt(
            digest_id=f"digest-{uuid4().hex}",
            recipient=digest.recipient,
            item_count=len(digest.items),
            dispatched_at=self._clock.now(),
            transport="recording",
        )
