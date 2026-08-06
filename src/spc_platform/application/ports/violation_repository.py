"""Persist and acknowledge rule violations (Module 3 / FR-A02)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.domain.ids import ActorId, ParameterId
from spc_platform.domain.violation import Violation


class StoredViolation(BaseModel):
    """A violation with a stable identity for acknowledgement."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    violation_id: str = Field(min_length=1)
    violation: Violation
    acknowledged: bool = False
    acknowledged_by: ActorId | None = None
    acknowledged_at: datetime | None = None


def new_stored_violation(violation: Violation) -> StoredViolation:
    """Assign a unique id to a freshly raised violation."""
    return StoredViolation(
        violation_id=f"vio-{uuid4().hex}",
        violation=violation,
    )


class ViolationRepository(Protocol):
    """Store violations raised by evaluate_lot and related use cases."""

    def save(self, stored: StoredViolation) -> None:
        """Insert or replace one stored violation."""
        ...

    def get(self, violation_id: str) -> StoredViolation | None:
        """Return the violation, or None if unknown."""
        ...

    def list_open(self, parameter_id: ParameterId | None = None) -> tuple[StoredViolation, ...]:
        """Return unacknowledged violations, newest first."""
        ...

    def acknowledge(
        self,
        violation_id: str,
        *,
        actor: ActorId,
        timestamp: datetime,
    ) -> StoredViolation:
        """Mark the violation acknowledged. Raises ``KeyError`` if unknown."""
        ...
