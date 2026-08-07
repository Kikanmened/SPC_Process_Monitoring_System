"""Wafer map marker budget: 5 000 sites within interaction budget; degrade above.

NFR-P04 / ADR-0018. The use case applies the budget; the test pins aggregation
behaviour and a warm assembly time under 1 s for a full-budget map.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from spc_platform.application.use_cases import get_wafer_map
from spc_platform.domain.enums import MeasurementStatus
from spc_platform.domain.ids import (
    ActorId,
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
from spc_platform.domain.wafer_map_view import MARKER_BUDGET
from spc_platform.infrastructure.composition import build_local_bundle

pytestmark = pytest.mark.performance

BUDGET_SECONDS = 1.0
WARMUP = 2
SAMPLES = 5
SEED_N = MARKER_BUDGET


def _seed(n: int) -> object:
    bundle = build_local_bundle()
    revision = DataRevision(f"rev-perf-{n}")
    start = datetime(2025, 7, 1, tzinfo=UTC)
    rows = [
        Measurement(
            measurement_id=MeasurementId(uuid4()),
            timestamp=start + timedelta(seconds=index),
            lot_id=LotId("LOT-PERF"),
            wafer_id=WaferId("LOT-PERF:1"),
            slot=1,
            site_id=SiteId((index % 49) + 1),
            site_x_mm=float(index % 100) - 50.0,
            site_y_mm=float((index // 100) % 100) - 50.0,
            parameter_id=ParameterId("OXIDE_THK"),
            value=10.0 + (index % 10) * 0.01,
            unit=UnitSymbol("nm"),
            step_id=StepId("OXIDE_GROW"),
            tool_id=ToolId("OX-01"),
            chamber_id=ChamberId("OX-01-A"),
            recipe_id=RecipeId("OX-STD-1"),
            product_id=ProductId("DEV-A"),
            metrology_tool_id=MetrologyToolId("MET-01"),
            measurement_status=MeasurementStatus.VALID,
            data_revision=revision,
        )
        for index in range(n)
    ]
    bundle.measurements.replace_revision(revision, tuple(rows))
    return bundle


def test_five_thousand_markers_assemble_under_one_second_warm() -> None:
    bundle = _seed(SEED_N)
    actor = ActorId("perf")

    def once() -> int:
        view = get_wafer_map(
            bundle.services,  # type: ignore[attr-defined]
            actor=actor,
            parameter_id=ParameterId("OXIDE_THK"),
            lot_id=LotId("LOT-PERF"),
            wafer_id=WaferId("LOT-PERF:1"),
            colour_vmin=9.0,
            colour_vmax=11.0,
        )
        return view.n_sites_total

    for _ in range(WARMUP):
        once()
    samples = []
    for _ in range(SAMPLES):
        started = time.perf_counter()
        total = once()
        samples.append(time.perf_counter() - started)
        assert total == SEED_N
    samples.sort()
    median = samples[len(samples) // 2]
    assert median < BUDGET_SECONDS


def test_above_budget_degrades_and_says_so() -> None:
    bundle = _seed(MARKER_BUDGET + 50)
    view = get_wafer_map(
        bundle.services,  # type: ignore[attr-defined]
        actor=ActorId("perf"),
        parameter_id=ParameterId("OXIDE_THK"),
        lot_id=LotId("LOT-PERF"),
        wafer_id=WaferId("LOT-PERF:1"),
        colour_vmin=9.0,
        colour_vmax=11.0,
    )
    assert view.is_aggregated is True
    assert view.aggregation_message is not None
    assert "Aggregated" in view.aggregation_message
    assert view.sites == ()
    assert view.aggregated
