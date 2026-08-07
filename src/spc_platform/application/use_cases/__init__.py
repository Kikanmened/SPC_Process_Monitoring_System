"""Application use cases — the only path API, CLI, and dashboard take into the domain."""

from spc_platform.application.use_cases.acknowledge_violation import acknowledge_violation
from spc_platform.application.use_cases.build_alarm_queue import build_alarm_queue
from spc_platform.application.use_cases.build_chart_view import build_chart_view
from spc_platform.application.use_cases.build_line_overview import build_line_overview
from spc_platform.application.use_cases.compare_tools import compare_tools
from spc_platform.application.use_cases.evaluate_lot import EvaluateLotResult, evaluate_lot
from spc_platform.application.use_cases.generate_capability_report import (
    CapabilityReportOutcome,
    generate_capability_report,
)
from spc_platform.application.use_cases.get_wafer_map import get_wafer_map
from spc_platform.application.use_cases.recompute_baseline import (
    RecomputeBaselineResult,
    recompute_baseline,
)
from spc_platform.application.use_cases.record_disposition import record_disposition
from spc_platform.application.use_cases.run_gauge_study import GaugeStudyOutcome, run_gauge_study
from spc_platform.application.views.chart_view import ChartView
from spc_platform.application.views.overview import LineOverview
from spc_platform.application.views.queue_view import AlarmQueueView
from spc_platform.application.views.tool_comparison import ToolComparisonView
from spc_platform.domain.wafer_map_view import WaferMapView

__all__ = [
    "AlarmQueueView",
    "CapabilityReportOutcome",
    "ChartView",
    "EvaluateLotResult",
    "GaugeStudyOutcome",
    "LineOverview",
    "RecomputeBaselineResult",
    "ToolComparisonView",
    "WaferMapView",
    "acknowledge_violation",
    "build_alarm_queue",
    "build_chart_view",
    "build_line_overview",
    "compare_tools",
    "evaluate_lot",
    "generate_capability_report",
    "get_wafer_map",
    "recompute_baseline",
    "record_disposition",
    "run_gauge_study",
]
