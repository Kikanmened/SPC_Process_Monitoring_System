"""Excursion lifecycle record (FR-A02 - FR-A04, FR-A07).

Cause is never stored here - only lifecycle state, OCAP linkage, disposition
references, and an 8D or CAPA identifier on closure.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from spc_platform.domain._time import require_aware
from spc_platform.domain.enums import ExcursionState
from spc_platform.domain.errors import DomainInvariantError
from spc_platform.domain.ids import (
    ActorId,
    CapaId,
    EightDId,
    ExcursionId,
    LotId,
    OcapId,
    ParameterId,
)


class Excursion(BaseModel):
    """One excursion from detection through optional closure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    excursion_id: ExcursionId
    parameter_id: ParameterId
    lot_ids: tuple[LotId, ...] = Field(min_length=1)
    violation_ids: tuple[str, ...] = Field(min_length=1)
    state: ExcursionState
    ocap_id: OcapId | None = None
    opened_at: datetime
    opened_by: ActorId
    containment_note: str | None = None
    contained_at: datetime | None = None
    investigation_summary: str | None = None
    investigated_at: datetime | None = None
    closed_at: datetime | None = None
    closed_by: ActorId | None = None
    capa_id: CapaId | None = None
    eight_d_id: EightDId | None = None

    @field_validator("opened_at", "contained_at", "investigated_at", "closed_at")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return require_aware(value, field_name="timestamp")

    @model_validator(mode="after")
    def _closure_requires_reference(self) -> Excursion:
        if self.state is ExcursionState.CLOSED:
            if self.capa_id is None and self.eight_d_id is None:
                msg = "closed excursion requires an 8D or CAPA identifier"
                raise DomainInvariantError(msg, excursion_id=str(self.excursion_id))
            if self.closed_at is None or self.closed_by is None:
                msg = "closed excursion requires closed_at and closed_by"
                raise DomainInvariantError(msg, excursion_id=str(self.excursion_id))
        return self
