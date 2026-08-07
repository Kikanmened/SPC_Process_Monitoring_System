"""Open-violation queue view (FR-A01)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.domain.enums import ViolationSeverity
from spc_platform.domain.ids import ParameterId


class AlarmQueueItem(BaseModel):
    """One open violation with OCAP linkage when known (FR-A04 display)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    violation_id: str
    parameter_id: ParameterId
    rule_id: str
    severity: ViolationSeverity
    timestamp: datetime
    statistic_value: float
    point_index: int
    baseline_id: str
    ocap_id: str | None = None
    acknowledged: bool = False


class AlarmQueueView(BaseModel):
    """Queue ordered by severity then age (newest first within severity)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    items: tuple[AlarmQueueItem, ...] = Field(default_factory=tuple)
    n_open: int = Field(ge=0)
    window_label: str = "open violations"
