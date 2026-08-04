"""Builders for domain objects so tests name the scenario, not the plumbing."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from spc_platform.domain import (
    ActorId,
    Baseline,
    BaselineId,
    BaselineStatus,
    ChamberId,
    ChartType,
    ControlLimit,
    DataRevision,
    LotId,
    Measurement,
    MeasurementId,
    MeasurementStatus,
    MetrologyToolId,
    ParameterId,
    ProductId,
    RecipeId,
    RuleDefinition,
    RuleId,
    RuleSet,
    SigmaEstimator,
    SiteId,
    SpecificationLimit,
    StepId,
    ToolId,
    UnitSymbol,
    ViolationSeverity,
    WaferId,
)


def aware(year: int = 2025, month: int = 6, day: int = 1, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=UTC)


def a_specification_limit(**overrides: object) -> SpecificationLimit:
    payload: dict[str, object] = {
        "parameter_id": ParameterId("OXIDE_THK"),
        "product_id": ProductId("DEV-A"),
        "step_id": StepId("OXIDE_GROW"),
        "unit": UnitSymbol("nm"),
        "lsl": 9.5,
        "usl": 10.5,
        "target": 10.0,
        "effective_from": aware(),
    }
    payload.update(overrides)
    return SpecificationLimit.model_validate(payload)


def a_control_limit(**overrides: object) -> ControlLimit:
    payload: dict[str, object] = {
        "parameter_id": ParameterId("OXIDE_THK"),
        "baseline_id": BaselineId("BL-OXIDE-001"),
        "unit": UnitSymbol("nm"),
        "centre_line": 10.0,
        "lcl": 9.7,
        "ucl": 10.3,
        "sigma_estimator": SigmaEstimator.MR_BAR_D2,
        "sigma_estimate": 0.1,
        "sigma_multiplier": 3.0,
        "effective_from": aware(),
    }
    payload.update(overrides)
    return ControlLimit.model_validate(payload)


def a_baseline(**overrides: object) -> Baseline:
    limits = a_control_limit()
    payload: dict[str, object] = {
        "baseline_id": limits.baseline_id,
        "parameter_id": limits.parameter_id,
        "status": BaselineStatus.ACTIVE,
        "n_observations": 50,
        "sigma_estimator": limits.sigma_estimator,
        "limits": limits,
        "window_start": aware(month=6, day=1),
        "window_end": aware(month=6, day=28),
        "approved_by": ActorId("qe.smith"),
        "approved_at": aware(month=6, day=30),
        "effective_from": aware(month=7, day=1),
    }
    payload.update(overrides)
    return Baseline.model_validate(payload)


def a_measurement(**overrides: object) -> Measurement:
    payload: dict[str, object] = {
        "measurement_id": MeasurementId(uuid4()),
        "timestamp": aware(),
        "lot_id": LotId("LOT-001"),
        "wafer_id": WaferId("LOT-001:1"),
        "slot": 1,
        "site_id": SiteId(1),
        "site_x_mm": 0.0,
        "site_y_mm": 0.0,
        "parameter_id": ParameterId("OXIDE_THK"),
        "value": 10.0,
        "unit": UnitSymbol("nm"),
        "step_id": StepId("OXIDE_GROW"),
        "tool_id": ToolId("OX-01"),
        "chamber_id": ChamberId("OX-01-A"),
        "recipe_id": RecipeId("OX-STD-1"),
        "product_id": ProductId("DEV-A"),
        "metrology_tool_id": MetrologyToolId("MET-ELLIP-01"),
        "measurement_status": MeasurementStatus.VALID,
        "data_revision": DataRevision("rev-001"),
    }
    payload.update(overrides)
    return Measurement.model_validate(payload)


def a_rule_set() -> RuleSet:
    return RuleSet(
        name="western_electric_1_4",
        rules=(
            RuleDefinition(
                rule_id=RuleId("WE1"),
                severity=ViolationSeverity.CRITICAL,
            ),
        ),
    )


def a_chart_type() -> ChartType:
    return ChartType.I_MR
