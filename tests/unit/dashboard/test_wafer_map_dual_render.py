"""Interactive and static renderers describe the same WaferMapView data."""

from __future__ import annotations

import pytest
from dashboard.components.wafer_map_figure import wafer_map_series_payload
from dashboard.components.wafer_map_static import wafer_map_static_arrays
from dashboard.theme.colour_scales import assert_scale_allowed, plotly_colorscale

from spc_platform.domain.enums import SpatialSignature
from spc_platform.domain.ids import (
    ChamberId,
    DataRevision,
    LotId,
    ParameterId,
    ToolId,
    UnitSymbol,
    WaferId,
)
from spc_platform.domain.wafer_map_view import (
    ColourScaleKind,
    ColourScaleLimits,
    ColourScaleMode,
    WaferMapView,
    WaferSiteView,
)


def _view(*, n: int = 5, vmin: float = 9.0, vmax: float = 11.0) -> WaferMapView:
    sites = tuple(
        WaferSiteView(
            site_id=index + 1,
            x_mm=float(index),
            y_mm=float(index % 2),
            value=10.0 + 0.1 * index,
            unit=UnitSymbol("nm"),
            slot=1,
            tool_id=ToolId("OX-01"),
            chamber_id=ChamberId("OX-01-A"),
            deviation_from_target=0.1 * index,
        )
        for index in range(n)
    )
    return WaferMapView(
        parameter_id=ParameterId("OXIDE_THK"),
        lot_id=LotId("LOT-1"),
        wafer_id=WaferId("LOT-1:1"),
        unit=UnitSymbol("nm"),
        sites=sites,
        colour_scale=ColourScaleLimits(
            vmin=vmin,
            vmax=vmax,
            mode=ColourScaleMode.FIXED,
            kind=ColourScaleKind.VIRIDIS,
            target=10.0,
        ),
        spatial_signature=SpatialSignature.NONE,
        spatial_statistic=0.0,
        target=10.0,
        data_revision=DataRevision("rev-1"),
        n_sites_total=n,
    )


def test_plotly_and_matplotlib_describe_identical_data() -> None:
    view = _view()
    plotly_payload = wafer_map_series_payload(view)
    static = wafer_map_static_arrays(view)
    assert plotly_payload["x"] == list(static.x)
    assert plotly_payload["y"] == list(static.y)
    assert plotly_payload["z"] == list(static.z)
    assert plotly_payload["vmin"] == static.vmin
    assert plotly_payload["vmax"] == static.vmax
    assert plotly_payload["n_sites_total"] == static.n_sites_total


def test_colour_scale_limits_are_identical_across_comparison_set() -> None:
    left = _view(vmin=9.5, vmax=10.5)
    right = _view(vmin=9.5, vmax=10.5)
    assert left.colour_scale.vmin == right.colour_scale.vmin
    assert left.colour_scale.vmax == right.colour_scale.vmax
    assert left.colour_scale.mode is ColourScaleMode.FIXED


def test_forbidden_scales_are_rejected() -> None:
    with pytest.raises(ValueError, match="forbidden"):
        assert_scale_allowed("Jet")
    assert plotly_colorscale(ColourScaleKind.VIRIDIS) == "Viridis"
