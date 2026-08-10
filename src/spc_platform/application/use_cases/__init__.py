"""Application use cases — the only path API, CLI, and dashboard take into the domain."""

from spc_platform.application.use_cases.acknowledge_violation import acknowledge_violation
from spc_platform.application.use_cases.advance_excursion import (
    contain_excursion,
    mark_excursion_dispositioned,
    record_excursion_investigation,
)
from spc_platform.application.use_cases.assemble_audit_package import (
    AuditPackageArtefact,
    assemble_audit_package,
)
from spc_platform.application.use_cases.build_alarm_queue import build_alarm_queue
from spc_platform.application.use_cases.build_chart_view import build_chart_view
from spc_platform.application.use_cases.build_line_overview import build_line_overview
from spc_platform.application.use_cases.close_excursion import close_excursion
from spc_platform.application.use_cases.compare_tools import compare_tools
from spc_platform.application.use_cases.dispatch_notifications import dispatch_notifications
from spc_platform.application.use_cases.evaluate_lot import EvaluateLotResult, evaluate_lot
from spc_platform.application.use_cases.generate_capability_report import (
    CapabilityReportOutcome,
    generate_capability_report,
)
from spc_platform.application.use_cases.generate_report import (
    GenerateReportRequest,
    generate_report,
)
from spc_platform.application.use_cases.get_wafer_map import get_wafer_map
from spc_platform.application.use_cases.open_excursion import open_excursion
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
    "AuditPackageArtefact",
    "CapabilityReportOutcome",
    "ChartView",
    "EvaluateLotResult",
    "GaugeStudyOutcome",
    "GenerateReportRequest",
    "LineOverview",
    "RecomputeBaselineResult",
    "ToolComparisonView",
    "WaferMapView",
    "acknowledge_violation",
    "assemble_audit_package",
    "build_alarm_queue",
    "build_chart_view",
    "build_line_overview",
    "close_excursion",
    "compare_tools",
    "contain_excursion",
    "dispatch_notifications",
    "evaluate_lot",
    "generate_capability_report",
    "generate_report",
    "get_wafer_map",
    "mark_excursion_dispositioned",
    "open_excursion",
    "recompute_baseline",
    "record_disposition",
    "record_excursion_investigation",
    "run_gauge_study",
]
