"""Chart, queue, overview, and tool comparison use cases."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from tests.factories.application import ACTOR, WINDOW_END, WINDOW_START, seeded_bundle
from tests.factories.domain import a_measurement

from spc_platform.application.use_cases import (
    build_alarm_queue,
    build_chart_view,
    build_line_overview,
    compare_tools,
    evaluate_lot,
    get_wafer_map,
)
from spc_platform.common.errors import InsufficientDataError
from spc_platform.domain.enums import MeasurementStatus
from spc_platform.domain.ids import (
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


def test_build_chart_view_marks_violations() -> None:
    bundle = seeded_bundle(outlier=11.5)
    view = build_chart_view(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        lot_id=LotId("LOT-001"),
    )
    assert view.n_observations >= 8
    assert view.ucl != view.specification_usl or view.specification_usl is not None
    assert any(point.violated for point in view.points)


def test_alarm_queue_orders_by_severity() -> None:
    bundle = seeded_bundle(outlier=11.5)
    evaluate_lot(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        lot_id=LotId("LOT-001"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )
    queue = build_alarm_queue(bundle.services, actor=ACTOR)
    assert queue.n_open >= 1
    overview = build_line_overview(
        bundle.services,
        actor=ACTOR,
        parameter_ids=(ParameterId("OXIDE_THK"),),
    )
    assert overview.rows[0].open_violations >= 1


def test_compare_tools_welch() -> None:
    bundle = build_local_bundle()
    revision = DataRevision("rev-tools")
    start = datetime(2025, 7, 1, tzinfo=UTC)
    rows: list[Measurement] = []
    for index in range(20):
        tool = ToolId("OX-01") if index < 10 else ToolId("OX-02")
        # Small within-group noise avoids Welch precision-loss warnings on
        # perfectly constant samples under filterwarnings=error.
        value = (10.0 if index < 10 else 10.5) + 0.01 * (index % 5)
        rows.append(
            Measurement(
                measurement_id=MeasurementId(uuid4()),
                timestamp=start + timedelta(hours=index),
                lot_id=LotId("LOT-T"),
                wafer_id=WaferId("LOT-T:1"),
                slot=1,
                site_id=SiteId(1),
                site_x_mm=0.0,
                site_y_mm=0.0,
                parameter_id=ParameterId("OXIDE_THK"),
                value=value,
                unit=UnitSymbol("nm"),
                step_id=StepId("OXIDE_GROW"),
                tool_id=tool,
                chamber_id=ChamberId("C-A"),
                recipe_id=RecipeId("R1"),
                product_id=ProductId("DEV-A"),
                metrology_tool_id=MetrologyToolId("M1"),
                measurement_status=MeasurementStatus.VALID,
                data_revision=revision,
            )
        )
    bundle.measurements.replace_revision(revision, tuple(rows))
    view = compare_tools(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        window_start=start,
        window_end=start + timedelta(days=2),
        group_a="OX-01",
        group_b="OX-02",
        group_by="tool",
    )
    assert view.test_name == "welch_t"
    assert view.p_value is not None
    assert view.n_total == 20


def test_compare_tools_missing_group() -> None:
    bundle = seeded_bundle()
    with pytest.raises(InsufficientDataError):
        compare_tools(
            bundle.services,
            actor=ACTOR,
            parameter_id=ParameterId("OXIDE_THK"),
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            group_a="MISSING",
            group_b="ALSO-MISSING",
        )


def test_get_wafer_map_aggregation_message_path() -> None:
    bundle = build_local_bundle()
    revision = DataRevision("rev-agg")
    start = datetime(2025, 7, 1, tzinfo=UTC)
    n = MARKER_BUDGET + 10
    rows = [
        a_measurement(
            data_revision=revision,
            value=10.0,
            timestamp=start + timedelta(seconds=i),
            site_id=SiteId((i % 40) + 1),
            site_x_mm=float(i % 50),
            site_y_mm=float(i % 37),
            lot_id=LotId("LOT-AGG"),
            wafer_id=WaferId("LOT-AGG:1"),
        )
        for i in range(n)
    ]
    bundle.measurements.replace_revision(revision, tuple(rows))
    view = get_wafer_map(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        lot_id=LotId("LOT-AGG"),
        wafer_id=WaferId("LOT-AGG:1"),
        colour_vmin=9.0,
        colour_vmax=11.0,
    )
    assert view.is_aggregated
    assert view.aggregation_message is not None
