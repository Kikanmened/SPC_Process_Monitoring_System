"""A rule signal at a plotted point (SYSTEM_ARCHITECTURE.md §3.1, FR-R04)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from spc_platform.domain._time import require_aware
from spc_platform.domain.enums import ChartType, ViolationSeverity
from spc_platform.domain.ids import BaselineId, ParameterId, RuleId


class Violation(BaseModel):
    """One recorded run-rule signal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    baseline_id: BaselineId
    rule_id: RuleId
    chart_type: ChartType
    severity: ViolationSeverity
    point_index: int = Field(ge=0)
    timestamp: datetime
    statistic_value: float

    @field_validator("timestamp")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return require_aware(value, field_name="timestamp")
