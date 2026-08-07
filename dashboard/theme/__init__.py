"""Visual tokens: limit styling and colour-vision-safe scales."""

from dashboard.theme.colour_scales import plotly_colorscale, sequential_scale_name
from dashboard.theme.limits import CONTROL_LIMIT_STYLE, SPEC_LIMIT_STYLE, VIOLATION_MARKER

__all__ = [
    "CONTROL_LIMIT_STYLE",
    "SPEC_LIMIT_STYLE",
    "VIOLATION_MARKER",
    "plotly_colorscale",
    "sequential_scale_name",
]
