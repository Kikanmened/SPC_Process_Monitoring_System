"""Port for digested violation notifications (FR-A05, FR-A06)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class DigestItem(BaseModel):
    """One violation line inside a digest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    violation_id: str
    parameter_id: str
    severity: str
    timestamp: datetime
    ocap_id: str | None = None
    escalated: bool = False


class NotificationDigest(BaseModel):
    """Grouped notifications for one recipient over a digest interval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recipient: str = Field(min_length=1)
    interval_seconds: int = Field(ge=1)
    items: tuple[DigestItem, ...] = Field(min_length=1)
    generated_at: datetime


class DispatchReceipt(BaseModel):
    """Proof a digest left the platform boundary."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    digest_id: str
    recipient: str
    item_count: int = Field(ge=1)
    dispatched_at: datetime
    transport: str


class Notifier(Protocol):
    """Dispatch a digest; never one notification per violation."""

    def dispatch(self, digest: NotificationDigest) -> DispatchReceipt:
        """Send the digest or raise ``NotificationDispatchError``."""
        ...
