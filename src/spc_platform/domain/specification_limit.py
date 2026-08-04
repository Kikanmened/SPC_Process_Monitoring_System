"""Customer / device requirement.

``lsl < target < usl``. Cannot be constructed from process data, and shares no
constructor or conversion with ``ControlLimit`` (FR-C06, ADR-0003).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from spc_platform.domain._time import require_aware
from spc_platform.domain.errors import DomainInvariantError
from spc_platform.domain.ids import ParameterId, ProductId, StepId, UnitSymbol


class SpecificationLimit(BaseModel):
    """An approved specification for one characteristic.

    Single-sided specifications leave the open side as ``None``. A two-sided
    specification requires ``lsl < target < usl`` when a target is present, or
    ``lsl < usl`` when it is not.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    product_id: ProductId
    step_id: StepId
    unit: UnitSymbol
    lsl: float | None = None
    usl: float | None = None
    target: float | None = None
    effective_from: datetime
    effective_to: datetime | None = None

    @model_validator(mode="after")
    def _invariants(self) -> SpecificationLimit:
        require_aware(self.effective_from, field_name="effective_from")
        if self.effective_to is not None:
            require_aware(self.effective_to, field_name="effective_to")
            if self.effective_to <= self.effective_from:
                raise DomainInvariantError(
                    "effective_to must be after effective_from",
                    effective_from=str(self.effective_from),
                    effective_to=str(self.effective_to),
                )
        if self.lsl is None and self.usl is None:
            raise DomainInvariantError(
                "at least one of lsl or usl is required",
                parameter_id=str(self.parameter_id),
            )
        if self.lsl is not None and self.usl is not None and self.lsl >= self.usl:
            raise DomainInvariantError(
                "lsl must be strictly less than usl",
                lsl=self.lsl,
                usl=self.usl,
            )
        if self.target is not None:
            if self.lsl is not None and not (self.lsl < self.target):
                raise DomainInvariantError(
                    "target must be greater than lsl",
                    lsl=self.lsl,
                    target=self.target,
                )
            if self.usl is not None and not (self.target < self.usl):
                raise DomainInvariantError(
                    "target must be less than usl",
                    usl=self.usl,
                    target=self.target,
                )
        return self
