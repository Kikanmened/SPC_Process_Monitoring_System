"""Render a ChartView as a Plotly figure — no statistics computed here."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

from dashboard.theme.limits import (
    CENTRE_LINE_STYLE,
    CONTROL_LIMIT_STYLE,
    SPEC_LIMIT_STYLE,
    VIOLATION_MARKER,
)
from spc_platform.application.views.chart_view import ChartView


def chart_figure(view: ChartView) -> go.Figure:
    """Build an individuals chart with distinct spec vs control limit styles."""
    x_labels = [point.timestamp.isoformat() for point in view.points]
    values = [point.value for point in view.points]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_labels,
            y=values,
            mode="lines+markers",
            name="Individual",
            marker={"size": 7, "color": "#334155"},
            line={"color": "#64748b", "width": 1},
        )
    )
    violated_x = [x_labels[p.index] for p in view.points if p.violated]
    violated_y = [p.value for p in view.points if p.violated]
    violated_text = [
        f"{VIOLATION_MARKER['label']}: {', '.join(p.rule_ids)}" for p in view.points if p.violated
    ]
    if violated_x:
        fig.add_trace(
            go.Scatter(
                x=violated_x,
                y=violated_y,
                mode="markers+text",
                name=str(VIOLATION_MARKER["label"]),
                text=violated_text,
                textposition="top center",
                marker={
                    "symbol": VIOLATION_MARKER["symbol"],
                    "size": VIOLATION_MARKER["size"],
                    "color": VIOLATION_MARKER["color"],
                    "line": {"width": VIOLATION_MARKER["line_width"], "color": "#000"},
                },
            )
        )

    def _hline(y: float, style: dict[str, Any], name: str) -> None:
        fig.add_hline(
            y=y,
            line=style["line"],
            annotation_text=name,
            annotation_position="right",
        )

    _hline(view.centre_line, dict(CENTRE_LINE_STYLE), str(CENTRE_LINE_STYLE["legend_label"]))
    _hline(view.ucl, dict(CONTROL_LIMIT_STYLE), f"{CONTROL_LIMIT_STYLE['annotation_prefix']} UCL")
    _hline(view.lcl, dict(CONTROL_LIMIT_STYLE), f"{CONTROL_LIMIT_STYLE['annotation_prefix']} LCL")
    if view.specification_usl is not None:
        _hline(
            view.specification_usl,
            dict(SPEC_LIMIT_STYLE),
            f"{SPEC_LIMIT_STYLE['annotation_prefix']} USL",
        )
    if view.specification_lsl is not None:
        _hline(
            view.specification_lsl,
            dict(SPEC_LIMIT_STYLE),
            f"{SPEC_LIMIT_STYLE['annotation_prefix']} LSL",
        )

    fig.update_layout(
        title=f"{view.parameter_id} · {view.chart_type.value} · n={view.n_observations}",
        xaxis_title="Time",
        yaxis_title=str(view.unit),
        template="plotly_white",
        legend_title="Series",
    )
    return fig


def chart_series_payload(view: ChartView) -> dict[str, object]:
    """Extract the data a figure describes — used by dual-render tests."""
    return {
        "values": [point.value for point in view.points],
        "timestamps": [point.timestamp.isoformat() for point in view.points],
        "lcl": view.lcl,
        "ucl": view.ucl,
        "centre_line": view.centre_line,
        "spec_lsl": view.specification_lsl,
        "spec_usl": view.specification_usl,
        "n": view.n_observations,
    }
