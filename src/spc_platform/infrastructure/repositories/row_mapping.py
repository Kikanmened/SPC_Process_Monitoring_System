"""Map between domain ``Measurement`` / ``Baseline`` and tabular rows."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from spc_platform.domain.baseline import Baseline
from spc_platform.domain.control_limit import ControlLimit
from spc_platform.domain.enums import (
    BaselineStatus,
    MeasurementStatus,
    SigmaEstimator,
)
from spc_platform.domain.ids import (
    ActorId,
    BaselineId,
    ChamberId,
    DataRevision,
    LotId,
    MeasurementId,
    MetrologyToolId,
    ParameterId,
    ProductId,
    RecipeId,
    SiteId,
    StepId,
    ToolId,
    UnitSymbol,
    WaferId,
)
from spc_platform.domain.measurement import Measurement

MEASUREMENT_COLUMNS: tuple[str, ...] = (
    "measurement_id",
    "timestamp",
    "lot_id",
    "wafer_id",
    "slot",
    "site_id",
    "site_x_mm",
    "site_y_mm",
    "parameter_id",
    "value",
    "unit",
    "step_id",
    "tool_id",
    "chamber_id",
    "recipe_id",
    "product_id",
    "metrology_tool_id",
    "measurement_status",
    "data_revision",
)

BASELINE_COLUMNS: tuple[str, ...] = (
    "baseline_id",
    "parameter_id",
    "status",
    "n_observations",
    "sigma_estimator",
    "centre_line",
    "lcl",
    "ucl",
    "sigma_estimate",
    "sigma_multiplier",
    "limits_unit",
    "window_start",
    "window_end",
    "approved_by",
    "approved_at",
    "supersedes",
    "effective_from",
)


def _utc_naive(value: datetime) -> datetime:
    """Return UTC wall time without tzinfo for engines that lack tz libraries.

    DuckDB's TIMESTAMPTZ binding pulls in ``pytz``; we store UTC-naive values
    and re-attach ``UTC`` on read so the domain boundary stays timezone-aware.
    """
    return value.astimezone(UTC).replace(tzinfo=None)


def measurement_to_row(item: Measurement) -> dict[str, Any]:
    """Flatten a measurement for persistence."""
    return {
        "measurement_id": str(item.measurement_id),
        "timestamp": _utc_naive(item.timestamp),
        "lot_id": str(item.lot_id),
        "wafer_id": str(item.wafer_id),
        "slot": item.slot,
        "site_id": int(item.site_id),
        "site_x_mm": item.site_x_mm,
        "site_y_mm": item.site_y_mm,
        "parameter_id": str(item.parameter_id),
        "value": item.value,
        "unit": str(item.unit),
        "step_id": str(item.step_id),
        "tool_id": str(item.tool_id),
        "chamber_id": str(item.chamber_id),
        "recipe_id": str(item.recipe_id),
        "product_id": str(item.product_id),
        "metrology_tool_id": str(item.metrology_tool_id),
        "measurement_status": item.measurement_status.value,
        "data_revision": str(item.data_revision),
    }


def measurement_from_row(row: dict[str, Any]) -> Measurement:
    """Rebuild a measurement from a persisted row."""
    timestamp = row["timestamp"]
    if isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    else:
        timestamp = timestamp.astimezone(UTC)
    return Measurement(
        measurement_id=MeasurementId(UUID(str(row["measurement_id"]))),
        timestamp=timestamp,
        lot_id=LotId(str(row["lot_id"])),
        wafer_id=WaferId(str(row["wafer_id"])),
        slot=int(row["slot"]),
        site_id=SiteId(int(row["site_id"])),
        site_x_mm=float(row["site_x_mm"]),
        site_y_mm=float(row["site_y_mm"]),
        parameter_id=ParameterId(str(row["parameter_id"])),
        value=float(row["value"]),
        unit=UnitSymbol(str(row["unit"])),
        step_id=StepId(str(row["step_id"])),
        tool_id=ToolId(str(row["tool_id"])),
        chamber_id=ChamberId(str(row["chamber_id"])),
        recipe_id=RecipeId(str(row["recipe_id"])),
        product_id=ProductId(str(row["product_id"])),
        metrology_tool_id=MetrologyToolId(str(row["metrology_tool_id"])),
        measurement_status=MeasurementStatus(str(row["measurement_status"])),
        data_revision=DataRevision(str(row["data_revision"])),
    )


def baseline_to_row(baseline: Baseline) -> dict[str, Any]:
    """Flatten a baseline and its limits for persistence."""
    return {
        "baseline_id": str(baseline.baseline_id),
        "parameter_id": str(baseline.parameter_id),
        "status": baseline.status.value,
        "n_observations": baseline.n_observations,
        "sigma_estimator": baseline.sigma_estimator.value,
        "centre_line": baseline.limits.centre_line,
        "lcl": baseline.limits.lcl,
        "ucl": baseline.limits.ucl,
        "sigma_estimate": baseline.limits.sigma_estimate,
        "sigma_multiplier": baseline.limits.sigma_multiplier,
        "limits_unit": str(baseline.limits.unit),
        "window_start": _utc_naive(baseline.window_start),
        "window_end": _utc_naive(baseline.window_end),
        "approved_by": None if baseline.approved_by is None else str(baseline.approved_by),
        "approved_at": (None if baseline.approved_at is None else _utc_naive(baseline.approved_at)),
        "supersedes": None if baseline.supersedes is None else str(baseline.supersedes),
        "effective_from": _utc_naive(baseline.effective_from),
    }


def _aware(value: datetime | str) -> datetime:
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def baseline_from_row(row: dict[str, Any]) -> Baseline:
    """Rebuild a baseline from a persisted row."""
    baseline_id = BaselineId(str(row["baseline_id"]))
    parameter_id = ParameterId(str(row["parameter_id"]))
    estimator = SigmaEstimator(str(row["sigma_estimator"]))
    limits = ControlLimit(
        parameter_id=parameter_id,
        baseline_id=baseline_id,
        unit=UnitSymbol(str(row["limits_unit"])),
        centre_line=float(row["centre_line"]),
        lcl=float(row["lcl"]),
        ucl=float(row["ucl"]),
        sigma_estimator=estimator,
        sigma_estimate=float(row["sigma_estimate"]),
        sigma_multiplier=float(row["sigma_multiplier"]),
        effective_from=_aware(row["effective_from"]),
    )
    approved_by = row["approved_by"]
    approved_at = row["approved_at"]
    supersedes = row["supersedes"]
    return Baseline(
        baseline_id=baseline_id,
        parameter_id=parameter_id,
        status=BaselineStatus(str(row["status"])),
        n_observations=int(row["n_observations"]),
        sigma_estimator=estimator,
        limits=limits,
        window_start=_aware(row["window_start"]),
        window_end=_aware(row["window_end"]),
        approved_by=None if approved_by is None else ActorId(str(approved_by)),
        approved_at=None if approved_at is None else _aware(approved_at),
        supersedes=None if supersedes is None else BaselineId(str(supersedes)),
        effective_from=_aware(row["effective_from"]),
    )
