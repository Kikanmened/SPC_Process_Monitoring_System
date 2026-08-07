"""Pure rendering widgets over application view models."""

from dashboard.components.chart_figure import chart_figure
from dashboard.components.refusal_panel import refusal_markdown
from dashboard.components.statistic_label import format_statistic
from dashboard.components.wafer_map_figure import wafer_map_figure
from dashboard.components.wafer_map_static import wafer_map_static_arrays

__all__ = [
    "chart_figure",
    "format_statistic",
    "refusal_markdown",
    "wafer_map_figure",
    "wafer_map_static_arrays",
]
