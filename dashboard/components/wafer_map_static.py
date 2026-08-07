"""Matplotlib static export from the same WaferMapView (ADR-0018)."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle

from dashboard.components.wafer_map_figure import wafer_map_series_payload
from spc_platform.domain.wafer_map_view import WaferMapView


@dataclass(frozen=True, slots=True)
class StaticWaferArrays:
    """Arrays a Matplotlib renderer would plot — compared to Plotly payload."""

    x: tuple[float, ...]
    y: tuple[float, ...]
    z: tuple[float, ...]
    vmin: float
    vmax: float
    n_sites_total: int
    mode: str
    aggregation_message: str | None


def wafer_map_static_arrays(view: WaferMapView) -> StaticWaferArrays:
    """Extract plot arrays from the view without inventing coordinates."""
    payload = wafer_map_series_payload(view)
    xs = payload["x"]
    ys = payload["y"]
    zs = payload["z"]
    vmin = payload["vmin"]
    vmax = payload["vmax"]
    n_total = payload["n_sites_total"]
    if not isinstance(xs, list) or not isinstance(ys, list) or not isinstance(zs, list):
        msg = "wafer_map_series_payload must provide list coordinates"
        raise TypeError(msg)
    if not isinstance(vmin, float | int) or not isinstance(vmax, float | int):
        msg = "wafer_map_series_payload colour limits must be numeric"
        raise TypeError(msg)
    if not isinstance(n_total, int):
        msg = "wafer_map_series_payload n_sites_total must be int"
        raise TypeError(msg)
    return StaticWaferArrays(
        x=tuple(float(v) for v in xs),
        y=tuple(float(v) for v in ys),
        z=tuple(float(v) for v in zs),
        vmin=float(vmin),
        vmax=float(vmax),
        n_sites_total=n_total,
        mode=str(payload["mode"]),
        aggregation_message=view.aggregation_message,
    )


def render_wafer_map_png_bytes(view: WaferMapView) -> bytes:
    """Render deterministic PNG bytes for export from the shared view arrays."""
    arrays = wafer_map_static_arrays(view)
    figure, axis = plt.subplots(figsize=(6, 6))
    scatter = axis.scatter(
        np.asarray(arrays.x),
        np.asarray(arrays.y),
        c=np.asarray(arrays.z),
        cmap="viridis",
        vmin=arrays.vmin,
        vmax=arrays.vmax,
    )
    circle = Circle(
        (0.0, 0.0),
        view.geometry.radius_mm,
        fill=False,
        edgecolor="black",
        linewidth=1.5,
    )
    axis.add_patch(circle)
    axis.set_aspect("equal")
    axis.set_xlabel("x (mm)")
    axis.set_ylabel("y (mm)")
    title = f"{view.parameter_id} n={arrays.n_sites_total}"
    if arrays.aggregation_message:
        title = f"{title}\n{arrays.aggregation_message}"
    axis.set_title(title)
    figure.colorbar(scatter, ax=axis, label=str(view.unit))
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=100)
    plt.close(figure)
    return buffer.getvalue()
