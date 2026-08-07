"""Control-chart view model for rendering (zero computation in the UI)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.domain.enums import ChartType, SigmaEstimator
from spc_platform.domain.ids import BaselineId, DataRevision, ParameterId, UnitSymbol


class ChartPoint(BaseModel):
    """One plotted point with violation markers for shape/label signalling."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int
    timestamp: datetime
    value: float
    violated: bool = False
    rule_ids: tuple[str, ...] = ()
    severities: tuple[str, ...] = ()


class ChartView(BaseModel):
    """Points, control limits, optional specification, and provenance for display."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    baseline_id: BaselineId
    chart_type: ChartType
    unit: UnitSymbol
    points: tuple[ChartPoint, ...]
    centre_line: float
    lcl: float
    ucl: float
    sigma_estimator: SigmaEstimator
    sigma_estimate: float
    specification_lsl: float | None = None
    specification_usl: float | None = None
    specification_target: float | None = None
    n_observations: int = Field(ge=0)
    window_start: datetime
    window_end: datetime
    data_revision: DataRevision
    config_revision: str
