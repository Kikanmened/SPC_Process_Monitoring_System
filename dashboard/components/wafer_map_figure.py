"""Plotly wafer map from WaferMapView — pure rendering (ADR-0018)."""

from __future__ import annotations

import math

import plotly.graph_objects as go

from dashboard.theme.colour_scales import plotly_colorscale
from spc_platform.domain.wafer_map_view import WaferMapView


def wafer_map_figure(view: WaferMapView) -> go.Figure:
    """Render sites (or aggregated bins) with fixed colour limits and geometry."""
    fig = go.Figure()
    radius = view.geometry.radius_mm
    _add_wafer_boundary(fig, radius, view.geometry.notch_angle_deg, view.geometry.exclusion_mm)

    scale = plotly_colorscale(view.colour_scale.kind)
    if view.is_aggregated:
        xs = [item.x_mm for item in view.aggregated]
        ys = [item.y_mm for item in view.aggregated]
        zs = [item.mean_value for item in view.aggregated]
        hover = [f"bin n={item.n_sites}<br>mean={item.mean_value:.4g}" for item in view.aggregated]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers",
                marker={
                    "size": 14,
                    "color": zs,
                    "colorscale": scale,
                    "cmin": view.colour_scale.vmin,
                    "cmax": view.colour_scale.vmax,
                    "colorbar": {
                        "title": f"{view.unit}<br>[{view.colour_scale.vmin:.4g}, "
                        f"{view.colour_scale.vmax:.4g}]"
                    },
                    "symbol": "square",
                },
                text=hover,
                hoverinfo="text",
                name="Aggregated",
            )
        )
    else:
        xs = [site.x_mm for site in view.sites]
        ys = [site.y_mm for site in view.sites]
        zs = [site.value for site in view.sites]
        hover = [
            (
                f"lot={view.lot_id}<br>wafer={view.wafer_id}<br>"
                f"slot={site.slot}<br>site={site.site_id}<br>"
                f"x={site.x_mm:.2f} mm, y={site.y_mm:.2f} mm<br>"
                f"value={site.value:.4g} {site.unit}<br>"
                f"tool={site.tool_id}<br>chamber={site.chamber_id}<br>"
                f"deviation={site.deviation_from_target}"
            )
            for site in view.sites
        ]
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=ys,
                mode="markers",
                marker={
                    "size": 10,
                    "color": zs,
                    "colorscale": scale,
                    "cmin": view.colour_scale.vmin,
                    "cmax": view.colour_scale.vmax,
                    "colorbar": {
                        "title": f"{view.unit}<br>[{view.colour_scale.vmin:.4g}, "
                        f"{view.colour_scale.vmax:.4g}]"
                    },
                },
                text=hover,
                hoverinfo="text",
                name="Sites",
            )
        )

    title = f"{view.parameter_id} · {view.wafer_id} · n={view.n_sites_total}"
    if view.is_aggregated and view.aggregation_message:
        title = f"{title}<br><sup>{view.aggregation_message}</sup>"
    if view.colour_scale.mode.value == "autoscale_labelled":
        title = f"{title}<br><sup>Colour scale: per-wafer autoscale (explicit)</sup>"

    fig.update_layout(
        title=title,
        xaxis_title="x (mm from centre)",
        yaxis_title="y (mm from centre)",
        yaxis_scaleanchor="x",
        template="plotly_white",
        width=700,
        height=700,
    )
    return fig


def wafer_map_series_payload(view: WaferMapView) -> dict[str, object]:
    """Return the series both Plotly and Matplotlib must describe identically."""
    if view.is_aggregated:
        return {
            "mode": "aggregated",
            "x": [item.x_mm for item in view.aggregated],
            "y": [item.y_mm for item in view.aggregated],
            "z": [item.mean_value for item in view.aggregated],
            "vmin": view.colour_scale.vmin,
            "vmax": view.colour_scale.vmax,
            "n_sites_total": view.n_sites_total,
        }
    return {
        "mode": "sites",
        "x": [site.x_mm for site in view.sites],
        "y": [site.y_mm for site in view.sites],
        "z": [site.value for site in view.sites],
        "vmin": view.colour_scale.vmin,
        "vmax": view.colour_scale.vmax,
        "n_sites_total": view.n_sites_total,
    }


def _add_wafer_boundary(
    fig: go.Figure,
    radius: float,
    notch_angle_deg: float,
    exclusion_mm: float,
) -> None:
    angles = [i * math.pi / 180.0 for i in range(361)]
    fig.add_trace(
        go.Scatter(
            x=[radius * math.cos(a) for a in angles],
            y=[radius * math.sin(a) for a in angles],
            mode="lines",
            line={"color": "#334155", "width": 2},
            name="Wafer boundary",
            hoverinfo="skip",
        )
    )
    if exclusion_mm > 0:
        inner = radius - exclusion_mm
        fig.add_trace(
            go.Scatter(
                x=[inner * math.cos(a) for a in angles],
                y=[inner * math.sin(a) for a in angles],
                mode="lines",
                line={"color": "#94a3b8", "width": 1, "dash": "dot"},
                name="Exclusion",
                hoverinfo="skip",
            )
        )
    notch = math.radians(notch_angle_deg)
    fig.add_trace(
        go.Scatter(
            x=[radius * math.cos(notch)],
            y=[radius * math.sin(notch)],
            mode="markers",
            marker={"symbol": "triangle-down", "size": 12, "color": "#0f172a"},
            name="Notch",
            hoverinfo="skip",
        )
    )
