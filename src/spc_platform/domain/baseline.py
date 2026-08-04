"""A qualified stable period used to compute control limits.

Immutable once approved; records n, estimator, and approver
(SYSTEM_ARCHITECTURE.md §3.1, FR-CF04).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spc_platform.domain._time import require_aware
from spc_platform.domain.control_limit import ControlLimit
from spc_platform.domain.enums import BaselineStatus, SigmaEstimator
from spc_platform.domain.errors import DomainInvariantError
from spc_platform.domain.ids import ActorId, BaselineId, ParameterId


class Baseline(BaseModel):
    """One versioned baseline for a parameter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline_id: BaselineId
    parameter_id: ParameterId
    status: BaselineStatus
    n_observations: int = Field(ge=2)
    sigma_estimator: SigmaEstimator
    limits: ControlLimit
    window_start: datetime
    window_end: datetime
    approved_by: ActorId | None = None
    approved_at: datetime | None = None
    supersedes: BaselineId | None = None
    effective_from: datetime

    @model_validator(mode="after")
    def _invariants(self) -> Baseline:
        require_aware(self.window_start, field_name="window_start")
        require_aware(self.window_end, field_name="window_end")
        require_aware(self.effective_from, field_name="effective_from")
        if self.window_end <= self.window_start:
            raise DomainInvariantError(
                "window_end must be after window_start",
                window_start=str(self.window_start),
                window_end=str(self.window_end),
            )
        if self.limits.parameter_id != self.parameter_id:
            raise DomainInvariantError(
                "limits.parameter_id must match baseline.parameter_id",
                baseline_parameter=str(self.parameter_id),
                limits_parameter=str(self.limits.parameter_id),
            )
        if self.limits.baseline_id != self.baseline_id:
            raise DomainInvariantError(
                "limits.baseline_id must match baseline.baseline_id",
                baseline_id=str(self.baseline_id),
                limits_baseline_id=str(self.limits.baseline_id),
            )
        if self.limits.sigma_estimator != self.sigma_estimator:
            raise DomainInvariantError(
                "limits.sigma_estimator must match baseline.sigma_estimator",
                baseline_estimator=self.sigma_estimator.value,
                limits_estimator=self.limits.sigma_estimator.value,
            )
        if self.status is BaselineStatus.ACTIVE and (
            self.approved_by is None or self.approved_at is None
        ):
            raise DomainInvariantError(
                "an active baseline requires approver and approval timestamp",
                baseline_id=str(self.baseline_id),
            )
        if self.approved_at is not None:
            require_aware(self.approved_at, field_name="approved_at")
        return self
