"""Matched-parameter tool/chamber comparison view (FR-T01 display)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.domain.ids import ParameterId, UnitSymbol


class ToolSeriesSummary(BaseModel):
    """Per-tool (or chamber) descriptive summary from the comparison use case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    group_key: str
    group_kind: str
    n_observations: int = Field(ge=0)
    mean: float
    sample_stdev: float | None = None


class ToolComparisonView(BaseModel):
    """Comparison result with the named statistical test stated (FR-T01)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    unit: UnitSymbol
    window_start: datetime
    window_end: datetime
    groups: tuple[ToolSeriesSummary, ...]
    test_name: str
    statistic: float | None = None
    p_value: float | None = None
    effect_size: float | None = None
    n_total: int = Field(ge=0)
    note: str = ""
