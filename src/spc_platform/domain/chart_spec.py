"""Per-parameter chart and rule-set configuration (FR-C02, FR-R03)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.domain.enums import ChartType, ViolationSeverity
from spc_platform.domain.ids import ParameterId, RuleId


class RuleDefinition(BaseModel):
    """One named run rule with a severity."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_id: RuleId
    severity: ViolationSeverity


class RuleSet(BaseModel):
    """The active rule set for a parameter — never a silent global default."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    rules: tuple[RuleDefinition, ...] = Field(min_length=1)


class ChartSpec(BaseModel):
    """Chart type and parameters selected from the control plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    chart_type: ChartType
    rule_set: RuleSet
    sigma_multiplier: float = Field(gt=0, default=3.0)
    ewma_lambda: float | None = Field(default=None, gt=0, lt=1)
    cusum_k: float | None = Field(default=None, gt=0)
    cusum_h: float | None = Field(default=None, gt=0)
