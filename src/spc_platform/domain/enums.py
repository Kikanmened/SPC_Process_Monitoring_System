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


class ChartStatistic(StrEnum):
    """What a single chart panel plots.

    A chart type is not the same thing as a plotted statistic: an X-bar/R chart
    draws two panels from one chart type, and its two panels have different
    centre lines, different limits, and different sensitivities. Naming the
    statistic separately is what lets a violation say which panel signalled.
    """

    INDIVIDUAL = "individual"
    MOVING_RANGE = "moving_range"
    SUBGROUP_MEAN = "subgroup_mean"
    SUBGROUP_RANGE = "subgroup_range"
    SUBGROUP_STDEV = "subgroup_stdev"
    EWMA = "ewma"
    CUSUM_UPPER = "cusum_upper"
    CUSUM_LOWER = "cusum_lower"
    PROPORTION_DEFECTIVE = "proportion_defective"
    COUNT_DEFECTIVE = "count_defective"
    COUNT_DEFECTS = "count_defects"
    DEFECTS_PER_UNIT = "defects_per_unit"


class SigmaEstimator(StrEnum):
    """Named sigma estimators. There is no unqualified ``sigma`` (FR-P03).

    The last three are not estimates of spread in the sense the first four are.
    On an attribute chart the spread is not measured at all: it is implied by
    the centre line through the assumed distribution. That has a consequence
    worth naming, which is why these appear here rather than being left blank —
    a p chart cannot distinguish "the level moved" from "the spread changed",
    because under the binomial the two are the same event.
    """

    MR_BAR_D2 = "mr_bar_d2"
    R_BAR_D2 = "r_bar_d2"
    S_BAR_C4 = "s_bar_c4"
    SAMPLE_STD = "sample_std"
    BINOMIAL = "binomial"
    POISSON = "poisson"
    LANEY = "laney"


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


class SpatialSignature(StrEnum):
    """Within-wafer spatial patterns (FR-S02, DATASET_GUIDE.md §4.2).

    ``NONE`` is a first-class outcome, not the residual left when nothing else
    fits. A classifier obliged to choose among the three named patterns will
    find one in noise (R-43), so the vocabulary has to let it say there is no
    signature at all.
    """

    NONE = "none"
    RADIAL = "radial"
    EDGE = "edge"
    ASYMMETRIC = "asymmetric"


class EquipmentState(StrEnum):
    """SEMI E10 equipment state vocabulary — conceptual alignment only."""

    PRODUCTIVE = "productive"
    STANDBY = "standby"
    ENGINEERING = "engineering"
    SCHEDULED_DOWNTIME = "scheduled_downtime"
    UNSCHEDULED_DOWNTIME = "unscheduled_downtime"
    NON_SCHEDULED = "non_scheduled"


class ExcursionState(StrEnum):
    """Lifecycle of an excursion investigation (FR-A01 - FR-A07)."""

    DETECTED = "detected"
    CONTAINED = "contained"
    INVESTIGATING = "investigating"
    DISPOSITIONED = "dispositioned"
    CLOSED = "closed"


class ReportType(StrEnum):
    """Approved report artefacts (FR-RP01)."""

    SPC_SUMMARY = "spc_summary"
    CAPABILITY_STUDY = "capability_study"
    MSA_REPORT = "msa_report"
    EXCURSION_SUMMARY = "excursion_summary"
