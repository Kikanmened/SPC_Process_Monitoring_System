"""Rational subgrouping for charting.

Every subgroup records the strategy that produced it (FR-C04). Sites within a
wafer are not a rational subgroup by default (R-04).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spc_platform.domain._time import require_aware
from spc_platform.domain.enums import SubgroupingKind
from spc_platform.domain.errors import DomainInvariantError
from spc_platform.domain.ids import LotId, ParameterId, WaferId


class SubgroupingStrategy(BaseModel):
    """The declared grouping policy for a parameter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: SubgroupingKind
    explicitly_declared: bool = True

    @model_validator(mode="after")
    def _sites_require_explicit_declaration(self) -> SubgroupingStrategy:
        if self.kind is SubgroupingKind.SITES_AS_SUBGROUP and not self.explicitly_declared:
            raise DomainInvariantError(
                "sites-as-subgroup requires an explicit declaration",
                kind=self.kind.value,
            )
        return self


class Subgroup(BaseModel):
    """One rational subgroup with the strategy that produced it stamped on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    strategy: SubgroupingStrategy
    values: tuple[float, ...] = Field(min_length=1)
    timestamp: datetime
    lot_id: LotId | None = None
    wafer_id: WaferId | None = None

    @model_validator(mode="after")
    def _invariants(self) -> Subgroup:
        require_aware(self.timestamp, field_name="timestamp")
        return self
