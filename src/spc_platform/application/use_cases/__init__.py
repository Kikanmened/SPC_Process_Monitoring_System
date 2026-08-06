"""Application use cases — the only path API and CLI take into the domain."""

from spc_platform.application.use_cases.acknowledge_violation import acknowledge_violation
from spc_platform.application.use_cases.evaluate_lot import EvaluateLotResult, evaluate_lot
from spc_platform.application.use_cases.generate_capability_report import (
    CapabilityReportOutcome,
    generate_capability_report,
)
from spc_platform.application.use_cases.get_wafer_map import WaferMapView, get_wafer_map
from spc_platform.application.use_cases.recompute_baseline import (
    RecomputeBaselineResult,
    recompute_baseline,
)
from spc_platform.application.use_cases.record_disposition import record_disposition
from spc_platform.application.use_cases.run_gauge_study import GaugeStudyOutcome, run_gauge_study

__all__ = [
    "CapabilityReportOutcome",
    "EvaluateLotResult",
    "GaugeStudyOutcome",
    "RecomputeBaselineResult",
    "WaferMapView",
    "acknowledge_violation",
    "evaluate_lot",
    "generate_capability_report",
    "get_wafer_map",
    "recompute_baseline",
    "record_disposition",
    "run_gauge_study",
]
