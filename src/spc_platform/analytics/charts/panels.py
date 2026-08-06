"""Assembly of chart panels, shared by every chart family.

The families differ in what they plot and in how wide their limits are. They do
not differ in the shape of the answer, so the assembly lives here once: a
statistic, its standard error, its limits, and the zones the rules read.

The one piece of arithmetic worth stating plainly is that limits are multiples
of the standard error of *the plotted point*, not of the process sigma. On an
X-bar chart with subgroups of five those differ by a factor of 2.24, and using
the wrong one produces a chart that looks entirely normal and signals either
constantly or never.

Constant and varying limits go through the same path. A chart whose limits
never move supplies one standard error; an attribute chart with a different
sample size at every point supplies one per point. NumPy broadcasting resolves
the difference, so there is no second code path for the case that gets less
testing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from spc_platform.common.errors import InsufficientDataError
from spc_platform.common.types import FloatArray
from spc_platform.domain.charting import ChartLimits, ChartPanel, PlottedSeries
from spc_platform.domain.enums import ChartStatistic, ChartType, SigmaEstimator
from spc_platform.domain.ids import BaselineId, ParameterId, UnitSymbol

ZONE_BOUNDARIES = (1.0, 2.0, 3.0)
"""Zone edges in standard errors: C ends at 1, B at 2, A at 3.

Western Electric's zones. They are fixed by the rules that read them, not
configurable — a "zone A" measured at something other than two to three
standard errors would silently change what every published rule means.
"""


@dataclass(frozen=True, slots=True)
class PanelIdentity:
    """What a panel is of, and which baseline it is judged against."""

    parameter_id: ParameterId
    baseline_id: BaselineId
    chart_type: ChartType
    statistic: ChartStatistic
    unit: UnitSymbol


@dataclass(frozen=True, slots=True)
class PlottedPoints:
    """The statistic to draw, with when and from how much it was computed."""

    values: FloatArray
    timestamps: tuple[datetime, ...]
    subgroup_sizes: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class LimitBasis:
    """Everything the limits are derived from.

    Attributes
    ----------
    centre_line
        Where the statistic is expected to sit. Constant even on charts whose
        limits vary: the pooled rate does not depend on how many units happened
        to be inspected at each point.
    sigma_statistic
        Standard error of a plotted point — one value if the same everywhere,
        otherwise one per point.
    sigma_process
        The process sigma the panel derives from, carried so a chart can state
        what it was drawn with.
    sigma_multiplier
        Limit width in standard errors, conventionally three.
    sigma_estimator
        Which estimator produced ``sigma_process``.
    floor, ceiling
        Bounds the statistic cannot cross, where it has them. A range or a
        standard deviation has a floor of zero; a proportion has both.

        A limit truncated onto the centre line is dropped rather than kept,
        because a limit sitting exactly where the statistic is expected to sit
        would signal on a point that is behaving perfectly. That is the CUSUM
        arm's case, and it is why one-sided panels exist.
    one_sided
        Draw only the upper limit. For a statistic that accumulates in one
        direction and is compared against a threshold from above, the lower side
        is not a limit that happens to be zero — it is not a limit.
    """

    centre_line: float
    sigma_statistic: FloatArray
    sigma_process: float
    sigma_multiplier: float
    sigma_estimator: SigmaEstimator
    floor: float | None = None
    ceiling: float | None = None
    one_sided: bool = False


def build_panel(
    identity: PanelIdentity,
    points: PlottedPoints,
    basis: LimitBasis,
) -> ChartPanel:
    """Assemble one drawn panel from its statistic and the limits it is judged against.

    Parameters
    ----------
    identity
        Parameter, baseline, chart type, statistic, and unit.
    points
        The plotted statistic with its timestamps and subgroup sizes.
    basis
        Centre line, standard errors, and the bounds of the statistic.

    Returns
    -------
    ChartPanel
        The series and its limits, which travel together from here on.

    Raises
    ------
    InsufficientDataError
        If no points were supplied, or the standard errors neither cover every
        point nor consist of a single constant value.
    """
    count = int(points.values.size)
    if count == 0:
        raise InsufficientDataError(
            "a chart panel needs at least one plotted point",
            statistic=identity.statistic,
            n=0,
            required=1,
        )
    spread = np.atleast_1d(np.asarray(basis.sigma_statistic, dtype=np.float64))
    if spread.size not in {1, count}:
        raise InsufficientDataError(
            "standard errors must be one constant or one value per plotted point",
            points=count,
            standard_errors=int(spread.size),
        )

    reach = basis.sigma_multiplier * spread
    lower = basis.centre_line - reach
    upper = basis.centre_line + reach
    if basis.floor is not None:
        lower = np.maximum(basis.floor, lower)
    if basis.ceiling is not None:
        upper = np.minimum(basis.ceiling, upper)
    drop_lower = basis.one_sided or bool(np.all(lower >= basis.centre_line))
    drop_upper = bool(np.all(upper <= basis.centre_line))

    series = PlottedSeries(
        parameter_id=identity.parameter_id,
        chart_type=identity.chart_type,
        statistic=identity.statistic,
        unit=identity.unit,
        values=tuple(float(value) for value in points.values),
        timestamps=points.timestamps,
        subgroup_sizes=points.subgroup_sizes,
    )
    limits = ChartLimits(
        parameter_id=identity.parameter_id,
        baseline_id=identity.baseline_id,
        chart_type=identity.chart_type,
        statistic=identity.statistic,
        unit=identity.unit,
        centre_line=(basis.centre_line,),
        lcl=None if drop_lower else _as_tuple(lower),
        ucl=None if drop_upper else _as_tuple(upper),
        sigma_statistic=_as_tuple(spread),
        sigma_multiplier=basis.sigma_multiplier,
        sigma_estimator=basis.sigma_estimator,
        sigma_process=basis.sigma_process,
    )
    return ChartPanel(series=series, limits=limits)


def standardised(panel: ChartPanel) -> FloatArray:
    """Express plotted points as distances from the centre line, in standard errors.

    Every run rule is expressed in these units, which is what allows one rule
    implementation to serve charts with fixed limits and charts whose limits
    move with the sample size.

    Parameters
    ----------
    panel
        The series and the limits it is judged against.

    Returns
    -------
    FloatArray
        One standardised value per plotted point.
    """
    values = np.asarray(panel.series.values, dtype=np.float64)
    centre = np.asarray(panel.limits.centre_line, dtype=np.float64)
    spread = np.asarray(panel.limits.sigma_statistic, dtype=np.float64)
    standard: FloatArray = (values - centre) / spread
    return standard


def _as_tuple(values: FloatArray) -> tuple[float, ...]:
    """Convert a limit array to the tuple the domain model stores."""
    return tuple(float(value) for value in np.atleast_1d(values))
