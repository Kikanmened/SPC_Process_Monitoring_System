"""Perceptually uniform, colour-vision-safe scales only (FR-S04, ADR-0018)."""

from __future__ import annotations

from spc_platform.domain.wafer_map_view import ColourScaleKind

_SEQUENTIAL = {
    ColourScaleKind.VIRIDIS: "Viridis",
    ColourScaleKind.CIVIDIS: "Cividis",
}

_FORBIDDEN = frozenset({"Jet", "Rainbow", "jet", "rainbow", "hsv", "HSV"})


def sequential_scale_name(kind: ColourScaleKind) -> str:
    """Return a Plotly sequential scale name, or raise for forbidden kinds."""
    if kind is ColourScaleKind.DIVERGING_TARGET:
        return "RdBu"
    name = _SEQUENTIAL.get(kind)
    if name is None or name in _FORBIDDEN:
        message = f"unsupported or forbidden colour scale: {kind}"
        raise ValueError(message)
    return name


def plotly_colorscale(kind: ColourScaleKind) -> str:
    """Map a view-model scale kind to a Plotly colorscale identifier."""
    return sequential_scale_name(kind)


def assert_scale_allowed(name: str) -> None:
    """Reject rainbow/jet by name (AC-S3)."""
    if name in _FORBIDDEN:
        message = f"colour scale {name!r} fabricates boundaries and is forbidden"
        raise ValueError(message)
