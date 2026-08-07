"""Seed a local bundle with a small demo series for Streamlit review."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from spc_platform.domain.baseline import Baseline
from spc_platform.domain.control_limit import ControlLimit
from spc_platform.domain.enums import BaselineStatus, MeasurementStatus, SigmaEstimator
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
from spc_platform.domain.specification_limit import SpecificationLimit
from spc_platform.infrastructure.composition import LocalBundle


def seed_demo_bundle(bundle: LocalBundle) -> None:
    """Load a short OXIDE_THK series, baseline, and specification if empty."""
    revision = DataRevision("rev-dashboard-demo")
    if bundle.measurements.has_revision(revision):
        return
    start = datetime(2025, 7, 1, 12, 0, tzinfo=UTC)
    values = (10.0, 10.05, 9.98, 10.02, 10.01, 9.99, 10.03, 10.0, 10.04, 9.97)
    rows: list[Measurement] = []
    for index, value in enumerate(values):
        tool = ToolId("OX-01") if index % 2 == 0 else ToolId("OX-02")
        chamber = ChamberId("OX-01-A") if index % 2 == 0 else ChamberId("OX-02-A")
        rows.append(
            Measurement(
                measurement_id=MeasurementId(uuid4()),
                timestamp=start + timedelta(hours=index),
                lot_id=LotId("LOT-DEMO"),
                wafer_id=WaferId("LOT-DEMO:1"),
                slot=1,
                site_id=SiteId((index % 9) + 1),
                site_x_mm=float((index % 3) - 1) * 40.0,
                site_y_mm=float((index // 3) % 3 - 1) * 40.0,
                parameter_id=ParameterId("OXIDE_THK"),
                value=value,
                unit=UnitSymbol("nm"),
                step_id=StepId("OXIDE_GROW"),
                tool_id=tool,
                chamber_id=chamber,
                recipe_id=RecipeId("OX-STD-1"),
                product_id=ProductId("DEV-A"),
                metrology_tool_id=MetrologyToolId("MET-ELLIP-01"),
                measurement_status=MeasurementStatus.VALID,
                data_revision=revision,
            )
        )
    bundle.measurements.replace_revision(revision, tuple(rows))
    parameter = ParameterId("OXIDE_THK")
    if bundle.baselines.active_for(parameter) is None:
        baseline_id = BaselineId("BL-DEMO-OXIDE")
        limits = ControlLimit(
            parameter_id=parameter,
            baseline_id=baseline_id,
            unit=UnitSymbol("nm"),
            centre_line=10.0,
            lcl=9.7,
            ucl=10.3,
            sigma_estimator=SigmaEstimator.MR_BAR_D2,
            sigma_estimate=0.1,
            sigma_multiplier=3.0,
            effective_from=datetime(2025, 6, 1, tzinfo=UTC),
        )
        bundle.baselines.save(
            Baseline(
                baseline_id=baseline_id,
                parameter_id=parameter,
                status=BaselineStatus.ACTIVE,
                n_observations=50,
                sigma_estimator=SigmaEstimator.MR_BAR_D2,
                limits=limits,
                window_start=datetime(2025, 5, 1, tzinfo=UTC),
                window_end=datetime(2025, 5, 28, tzinfo=UTC),
                approved_by=ActorId("qe.smith"),
                approved_at=datetime(2025, 5, 30, tzinfo=UTC),
                effective_from=datetime(2025, 6, 1, tzinfo=UTC),
            )
        )
    if (
        bundle.specifications.effective_for(
            parameter,
            ProductId("DEV-A"),
            at=start + timedelta(days=30),
        )
        is None
    ):
        bundle.specifications.save(
            SpecificationLimit(
                parameter_id=parameter,
                product_id=ProductId("DEV-A"),
                step_id=StepId("OXIDE_GROW"),
                unit=UnitSymbol("nm"),
                lsl=9.5,
                usl=10.5,
                target=10.0,
                effective_from=datetime(2025, 1, 1, tzinfo=UTC),
            )
        )
