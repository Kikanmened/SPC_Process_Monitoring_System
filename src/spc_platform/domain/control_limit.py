"""Process-derived control boundary.

Carries baseline ID, sigma estimator, and effective date. **Cannot be
constructed from a specification** — there is no conversion path to or from
``SpecificationLimit`` (FR-C06, ADR-0003).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spc_platform.domain._time import require_aware
from spc_platform.domain.enums import SigmaEstimator
from spc_platform.domain.errors import DomainInvariantError
from spc_platform.domain.ids import BaselineId, ParameterId, UnitSymbol


class ControlLimit(BaseModel):
    """Centre line and control limits derived from a qualified baseline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    baseline_id: BaselineId
    unit: UnitSymbol
    centre_line: float
    lcl: float
    ucl: float
    sigma_estimator: SigmaEstimator
    sigma_estimate: float = Field(gt=0)
    sigma_multiplier: float = Field(gt=0, default=3.0)
    effective_from: datetime

    @model_validator(mode="after")
    def _invariants(self) -> ControlLimit:
        require_aware(self.effective_from, field_name="effective_from")
        if not (self.lcl < self.centre_line < self.ucl):
            raise DomainInvariantError(
                "require lcl < centre_line < ucl",
                lcl=self.lcl,
                centre_line=self.centre_line,
                ucl=self.ucl,
            )
        return self
