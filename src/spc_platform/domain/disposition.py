"""Recorded human decision about affected material (FR-A03)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from spc_platform.domain._time import require_aware
from spc_platform.domain.enums import DispositionAction
from spc_platform.domain.ids import ActorId, LotId, OcapId


class Disposition(BaseModel):
    """A disposition with actor, timestamp, and mandatory reason."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lot_id: LotId
    action: DispositionAction
    actor: ActorId
    timestamp: datetime
    reason: str = Field(min_length=1)
    ocap_id: OcapId | None = None

    @field_validator("timestamp")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return require_aware(value, field_name="timestamp")

    @field_validator("reason")
    @classmethod
    def _reason_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "reason must not be blank"
            raise ValueError(msg)
        return stripped
