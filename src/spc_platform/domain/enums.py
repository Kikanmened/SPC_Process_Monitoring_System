"""Enumerated domain states. Bare strings are never used for these concepts."""

from __future__ import annotations

from enum import StrEnum


class MeasurementStatus(StrEnum):
    """Lifecycle of a measurement record (DATASET_GUIDE.md §3.1)."""

    VALID = "valid"
    REMEASURED = "remeasured"
    SUPERSEDED = "superseded"
    SUSPECT = "suspect"


class DispositionAction(StrEnum):
    """Permitted material dispositions (GLOSSARY.md §3)."""

    CONTINUE = "continue"
    HOLD = "hold"
    REWORK = "rework"
    SCRAP = "scrap"
    USE_AS_IS = "use-as-is"


class ChartType(StrEnum):
    """Supported control chart families (FR-C01)."""

    I_MR = "i-mr"
    XBAR_R = "xbar-r"
    XBAR_S = "xbar-s"
    EWMA = "ewma"
    CUSUM = "cusum"
    P = "p"
    NP = "np"
    C = "c"
    U = "u"


class SigmaEstimator(StrEnum):
    """Named sigma estimators. There is no unqualified ``sigma`` (FR-P03)."""

    MR_BAR_D2 = "mr_bar_d2"
    R_BAR_D2 = "r_bar_d2"
    S_BAR_C4 = "s_bar_c4"
    SAMPLE_STD = "sample_std"


class ViolationSeverity(StrEnum):
    """Severity attached to a rule signal."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class BaselineStatus(StrEnum):
    """Lifecycle of a baseline version."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class SubgroupingKind(StrEnum):
    """How measurements are grouped for charting (FR-C04).

    ``SITES_AS_SUBGROUP`` is refused unless the parameter declares it explicitly
    — sites within a wafer are not a rational subgroup by default (R-04).
    """

    WAFER_MEAN = "wafer_mean"
    LOT_MEAN = "lot_mean"
    TIME_WINDOW = "time_window"
    SITES_AS_SUBGROUP = "sites_as_subgroup"


class EquipmentState(StrEnum):
    """SEMI E10 equipment state vocabulary — conceptual alignment only."""

    PRODUCTIVE = "productive"
    STANDBY = "standby"
    ENGINEERING = "engineering"
    SCHEDULED_DOWNTIME = "scheduled_downtime"
    UNSCHEDULED_DOWNTIME = "unscheduled_downtime"
    NON_SCHEDULED = "non_scheduled"
