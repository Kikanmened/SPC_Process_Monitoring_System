"""Charts for continuous measurements: individuals with moving range, X-bar/R, X-bar/S.

Which of the three applies is a question about the data, not a preference.
Individuals when one measurement exists per opportunity — a furnace run, a
daily assay. X-bar/R when subgroups are small, where the range is nearly as
efficient as the standard deviation and far easier to compute by hand, which is
the historical reason it dominates. X-bar/S when subgroups exceed roughly ten,
where the range starts discarding real information because it looks only at two
of the observations.

References
----------
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §6.2 (X-bar/R), §6.3 (X-bar/S), §6.4 (individuals).
NIST/SEMATECH e-Handbook of Statistical Methods, §6.3.2.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spc_platform.analytics.charts.panels import (
    LimitBasis,
    PanelIdentity,
    PlottedPoints,
    build_panel,
)
from spc_platform.analytics.charts.study import ChartStudy, PanelEstimate
from spc_platform.analytics.estimators.constants import c4, d2, d3
from spc_platform.analytics.estimators.sigma import (
    MOVING_RANGE_SPAN,
    moving_ranges,
    sigma_within_moving_range,
    sigma_within_range,
    sigma_within_stdev,
    subgroup_ranges,
    subgroup_stdevs,
)
from spc_platform.common.errors import InsufficientDataError
from spc_platform.common.types import FloatArray, FloatMatrix
from spc_platform.domain.charting import ChartPanel
from spc_platform.domain.enums import ChartStatistic, ChartType, SigmaEstimator

DEFAULT_SIGMA_MULTIPLIER = 3.0
"""Three standard errors, giving a false alarm about once in 370 points.

Configurable per parameter through ``ChartSpec``. Changing it changes what
every alarm on that parameter means, which is why it is recorded on the limits
rather than assumed by a reader.
"""

MIN_SUBGROUPS_FOR_STUDY = 2
"""A single subgroup gives a centre line and no idea of its uncertainty.

Montgomery recommends 20 to 25 for a real Phase I study. Two is what the
arithmetic requires; the gap between the two numbers is a matter for the
application layer, which knows whether it is looking at a validated baseline or
a first look at new equipment.
"""


def individuals_study(
    values: FloatArray,
    *,
    sigma_multiplier: float = DEFAULT_SIGMA_MULTIPLIER,
    span: int = MOVING_RANGE_SPAN,
) -> ChartStudy:
    r"""Estimate I-MR limits from a run of individual measurements.

    The individuals limits are :math:`\bar{x} \pm 3 \overline{MR}/d_2`, which
    is the familiar :math:`E_2 \overline{MR}` written out. The moving range
    limits are :math:`D_3 \overline{MR}` and :math:`D_4 \overline{MR}` for the
    span used, so for the usual span of two the lower limit is zero.

    Parameters
    ----------
    values
        Individual measurements in time order, in the measurement's own unit.
    sigma_multiplier
        Limit width in standard errors.
    span
        Moving range span, two unless there is a documented reason otherwise.

    Returns
    -------
    ChartStudy
        Location panel of individuals, dispersion panel of moving ranges.

    Raises
    ------
    InsufficientDataError
        If there are too few observations to form a moving range.
    DegenerateSeriesError
        If every observation is identical.

    References
    ----------
    Montgomery (2019), 8th ed., §6.4, Equations 6.24-6.26.
    NIST/SEMATECH e-Handbook, §6.3.2.4.
    """
    estimate = sigma_within_moving_range(values, span)
    centre = float(np.mean(values))
    ranges = moving_ranges(values, span)
    mean_range = float(np.mean(ranges))

    location = _panel_estimate(
        statistic=ChartStatistic.INDIVIDUAL,
        centre_line=centre,
        sigma_statistic=estimate.value,
        sigma_multiplier=sigma_multiplier,
    )
    dispersion = _panel_estimate(
        statistic=ChartStatistic.MOVING_RANGE,
        centre_line=mean_range,
        sigma_statistic=sigma_of_range(estimate.value, span),
        sigma_multiplier=sigma_multiplier,
        floor=0.0,
    )
    return ChartStudy(
        chart_type=ChartType.I_MR,
        location=location,
        dispersion=dispersion,
        sigma_within=estimate,
        n_subgroups=int(values.size),
        subgroup_size=span,
    )


@dataclass(frozen=True, slots=True)
class FixedIndividualsLimits:
    """Phase II limits for an individuals chart, fixed before the points arrive.

    Attributes
    ----------
    centre_line
        Process centre the points are judged against.
    sigma_within
        Short-term sigma; the standard error of an individual point.
    sigma_multiplier
        Limit width in standard errors.
    sigma_estimator
        Which estimator produced ``sigma_within``, recorded on the limits.
    """

    centre_line: float
    sigma_within: float
    sigma_multiplier: float = DEFAULT_SIGMA_MULTIPLIER
    sigma_estimator: SigmaEstimator = SigmaEstimator.MR_BAR_D2


def individuals_chart(
    points: PlottedPoints,
    identity: PanelIdentity,
    limits: FixedIndividualsLimits,
) -> ChartPanel:
    """Plot individuals against limits fixed beforehand (Phase II).

    The limits come from a prior Phase I study or an approved baseline. There
    is no path here that recomputes them from ``points`` — that would be the
    Phase I/II conflation FR-C03 exists to prevent.

    Parameters
    ----------
    points
        Individual observations in time order with their timestamps.
    identity
        Parameter, baseline, chart type, statistic, and unit.
    limits
        Fixed centre, short-term sigma, multiplier, and estimator identity.

    Returns
    -------
    ChartPanel
        The individuals series with its fixed limits.

    Raises
    ------
    InsufficientDataError
        If no points were supplied, or the short-term sigma is not positive.
    """
    if limits.sigma_within <= 0.0:
        raise InsufficientDataError(
            "Phase II limits need a positive short-term sigma",
            sigma_within=limits.sigma_within,
        )
    return build_panel(
        identity,
        points,
        LimitBasis(
            centre_line=limits.centre_line,
            sigma_statistic=np.asarray([limits.sigma_within], dtype=np.float64),
            sigma_process=limits.sigma_within,
            sigma_multiplier=limits.sigma_multiplier,
            sigma_estimator=limits.sigma_estimator,
        ),
    )


def xbar_r_study(
    subgroups: FloatMatrix,
    *,
    sigma_multiplier: float = DEFAULT_SIGMA_MULTIPLIER,
) -> ChartStudy:
    r"""Estimate X-bar/R limits from equal-sized subgroups.

    Limits are :math:`\bar{\bar{x}} \pm A_2 \bar{R}` on the means and
    :math:`D_3 \bar{R}`, :math:`D_4 \bar{R}` on the ranges. This function
    computes them as three standard errors of the plotted statistic, which is
    the same arithmetic written so that the standard error is visible: the
    limit factors exist to save the hand computation of
    :math:`3\bar{R}/(d_2\sqrt{n})`, not to define anything different.

    Parameters
    ----------
    subgroups
        Two-dimensional, one row per subgroup, equal sizes, in time order.
    sigma_multiplier
        Limit width in standard errors.

    Returns
    -------
    ChartStudy
        Location panel of subgroup means, dispersion panel of ranges.

    Raises
    ------
    InsufficientDataError
        If there are fewer than two subgroups, or subgroups below size two.
    DegenerateSeriesError
        If every subgroup range is zero.

    References
    ----------
    Montgomery (2019), 8th ed., §6.2.1, Equations 6.4-6.7.
    """
    _require_subgroups(subgroups)
    estimate = sigma_within_range(subgroups)
    grand_mean = float(np.mean(subgroups))
    mean_range = float(np.mean(subgroup_ranges(subgroups)))
    subgroup_size = int(subgroups.shape[1])

    location = _panel_estimate(
        statistic=ChartStatistic.SUBGROUP_MEAN,
        centre_line=grand_mean,
        sigma_statistic=estimate.value / float(np.sqrt(subgroup_size)),
        sigma_multiplier=sigma_multiplier,
    )
    dispersion = _panel_estimate(
        statistic=ChartStatistic.SUBGROUP_RANGE,
        centre_line=mean_range,
        sigma_statistic=sigma_of_range(estimate.value, subgroup_size),
        sigma_multiplier=sigma_multiplier,
        floor=0.0,
    )
    return ChartStudy(
        chart_type=ChartType.XBAR_R,
        location=location,
        dispersion=dispersion,
        sigma_within=estimate,
        n_subgroups=int(subgroups.shape[0]),
        subgroup_size=subgroup_size,
    )


def xbar_s_study(
    subgroups: FloatMatrix,
    *,
    sigma_multiplier: float = DEFAULT_SIGMA_MULTIPLIER,
) -> ChartStudy:
    r"""Estimate X-bar/S limits from equal-sized subgroups.

    Limits are :math:`\bar{\bar{x}} \pm A_3 \bar{s}` on the means and
    :math:`B_3 \bar{s}`, :math:`B_4 \bar{s}` on the standard deviations.

    Parameters
    ----------
    subgroups
        Two-dimensional, one row per subgroup, equal sizes, in time order.
    sigma_multiplier
        Limit width in standard errors.

    Returns
    -------
    ChartStudy
        Location panel of subgroup means, dispersion panel of standard
        deviations.

    Raises
    ------
    InsufficientDataError
        If there are fewer than two subgroups, or subgroups below size two.
    DegenerateSeriesError
        If every subgroup standard deviation is zero.

    References
    ----------
    Montgomery (2019), 8th ed., §6.3.1, Equations 6.24-6.28.
    """
    _require_subgroups(subgroups)
    estimate = sigma_within_stdev(subgroups)
    grand_mean = float(np.mean(subgroups))
    mean_stdev = float(np.mean(subgroup_stdevs(subgroups)))
    subgroup_size = int(subgroups.shape[1])

    location = _panel_estimate(
        statistic=ChartStatistic.SUBGROUP_MEAN,
        centre_line=grand_mean,
        sigma_statistic=estimate.value / float(np.sqrt(subgroup_size)),
        sigma_multiplier=sigma_multiplier,
    )
    dispersion = _panel_estimate(
        statistic=ChartStatistic.SUBGROUP_STDEV,
        centre_line=mean_stdev,
        sigma_statistic=sigma_of_stdev(estimate.value, subgroup_size),
        sigma_multiplier=sigma_multiplier,
        floor=0.0,
    )
    return ChartStudy(
        chart_type=ChartType.XBAR_S,
        location=location,
        dispersion=dispersion,
        sigma_within=estimate,
        n_subgroups=int(subgroups.shape[0]),
        subgroup_size=subgroup_size,
    )


def sigma_of_range(sigma_process: float, subgroup_size: int) -> float:
    r"""Give the standard error of a subgroup range: :math:`d_3 \sigma`.

    Parameters
    ----------
    sigma_process
        Process standard deviation.
    subgroup_size
        Observations per subgroup.

    Returns
    -------
    float
        Standard deviation of the range statistic.

    References
    ----------
    Montgomery (2019), 8th ed., §6.2.1.
    """
    return d3(subgroup_size) * sigma_process


def sigma_of_stdev(sigma_process: float, subgroup_size: int) -> float:
    r"""Give the standard error of a subgroup standard deviation.

    Parameters
    ----------
    sigma_process
        Process standard deviation.
    subgroup_size
        Observations per subgroup.

    Returns
    -------
    float
        Standard deviation of the s statistic.

    References
    ----------
    Montgomery (2019), 8th ed., §6.3.1.
    """
    return sigma_process * float(np.sqrt(1.0 - c4(subgroup_size) ** 2))


def _panel_estimate(
    *,
    statistic: ChartStatistic,
    centre_line: float,
    sigma_statistic: float,
    sigma_multiplier: float,
    floor: float | None = None,
) -> PanelEstimate:
    """One panel's centre and limits, at whatever multiplier was configured.

    Every variables panel is this same construction. The published factors —
    A2, D3, D4, B3, B4 — are this arithmetic pre-multiplied for a three-sigma
    chart and a table of d2, d3, and c4; they are not separate definitions. So
    writing it once in the general form covers configured multipliers other
    than three, which the factor tables cannot, and
    ``tests/statistical/analytics/test_variables_charts.py`` asserts the two
    agree exactly where the tables apply.

    ``floor`` is the value the statistic cannot go below, where it has one. If
    three standard errors reaches past it, the panel records that it has no
    lower limit rather than drawing the floor as though crossing it were
    possible.
    """
    reach = sigma_multiplier * sigma_statistic
    lower = centre_line - reach
    reachable = floor is None or lower > floor
    if floor is not None:
        lower = max(floor, lower)
    return PanelEstimate(
        statistic=statistic,
        centre_line=centre_line,
        lcl=lower,
        ucl=centre_line + reach,
        sigma_statistic=sigma_statistic,
        has_lower_limit=reachable,
    )


def mean_range_for_sigma(sigma_process: float, subgroup_size: int) -> float:
    r"""Give the mean range a process of this sigma produces: :math:`d_2 \sigma`.

    Needed when charting from a baseline, which records the process sigma
    rather than the mean range the Phase I study happened to see.

    Parameters
    ----------
    sigma_process
        Process standard deviation.
    subgroup_size
        Observations per subgroup.

    Returns
    -------
    float
        Expected mean range.

    References
    ----------
    Montgomery (2019), 8th ed., §6.2.1.
    """
    return d2(subgroup_size) * sigma_process


def mean_stdev_for_sigma(sigma_process: float, subgroup_size: int) -> float:
    r"""Give the mean subgroup standard deviation a process of this sigma produces.

    :math:`c_4 \sigma`, the counterpart of :func:`mean_range_for_sigma`.

    Parameters
    ----------
    sigma_process
        Process standard deviation.
    subgroup_size
        Observations per subgroup.

    Returns
    -------
    float
        Expected mean subgroup standard deviation.

    References
    ----------
    Montgomery (2019), 8th ed., §6.3.1.
    """
    return c4(subgroup_size) * sigma_process


def _require_subgroups(subgroups: FloatMatrix) -> None:
    """Reject a study with too few subgroups to estimate anything from.

    Raises
    ------
    InsufficientDataError
        If fewer than two subgroups are supplied.
    """
    if subgroups.ndim == 0 or subgroups.shape[0] < MIN_SUBGROUPS_FOR_STUDY:
        raise InsufficientDataError(
            "a Phase I study needs at least two subgroups",
            n=int(subgroups.shape[0]) if subgroups.ndim else 0,
            required=MIN_SUBGROUPS_FOR_STUDY,
        )
