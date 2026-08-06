"""Estimators of process variation, each carrying the identity of its method.

Two numbers in this module answer questions that sound the same and are not.
``sigma_within`` describes the variation the process shows over a few
consecutive units; ``sigma_overall`` describes the variation it shows across
the whole record, including every drift and step between one shift and the
next. On a real fab process the second is routinely twice the first.

Which one belongs in a calculation is not a matter of preference. Control
limits use within, because a chart that widened itself with the process's own
drift could never signal that drift. Capability against a customer requirement
uses overall, because the customer receives all the material, not a
well-behaved window of it. Quoting one where the other belongs is the single
most common way a capability index is overstated, and it does not look like an
error — it looks like a better process.

Every function here returns a :class:`SigmaEstimate`, which names the method
used. Callers therefore cannot hold an anonymous float and forget which
question it answered.

References
----------
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §6.2-6.4 (chart estimators) and §8.3 (within versus overall).
NIST/SEMATECH e-Handbook of Statistical Methods, §6.3.2 and §6.1.6.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spc_platform.analytics.estimators.constants import (
    MAX_TABULATED_SUBGROUP_SIZE,
    MIN_SUBGROUP_SIZE,
    c4,
    d2,
)
from spc_platform.common.errors import DegenerateSeriesError, InsufficientDataError
from spc_platform.common.types import FloatArray, FloatMatrix
from spc_platform.domain.enums import SigmaEstimator

MOVING_RANGE_SPAN = 2
"""Observations spanned by the conventional moving range.

Two is not an arbitrary default. The moving range of consecutive individuals is
what makes an individuals chart's estimate short-term: a wider span absorbs
more of the drift the chart exists to detect.
"""

MIN_MOVING_RANGE_OBSERVATIONS = 2
"""One observation has no neighbour, so no moving range and no estimate."""

_SUBGROUP_AXES = 2
"""Subgrouped data is a rectangle: subgroups down, observations across."""


@dataclass(frozen=True, slots=True)
class SigmaEstimate:
    """A dispersion estimate, inseparable from the method that produced it.

    Attributes
    ----------
    value
        The estimate, in the unit of the measurements it came from.
    estimator
        Which method produced it. Carried into ``ControlLimit`` so that any
        chart can state how its limits were derived.
    subgroup_size
        Observations per subgroup, or the moving range span for individuals.
    n_subgroups
        Subgroups the estimate averages over. Reported because an estimate from
        five subgroups and one from a hundred deserve different confidence and
        look identical once reduced to a float.
    """

    value: float
    estimator: SigmaEstimator
    subgroup_size: int
    n_subgroups: int


def moving_ranges(values: FloatArray, span: int = MOVING_RANGE_SPAN) -> FloatArray:
    """Absolute differences between observations ``span - 1`` apart.

    Parameters
    ----------
    values
        Individual observations in time order.
    span
        Observations each range covers. Two gives the usual
        ``|x[i] - x[i-1]|``.

    Returns
    -------
    FloatArray
        ``len(values) - span + 1`` ranges. Shorter than the input by design:
        the first observations have no predecessor, and padding the result to
        match would invent a range that was never measured.

    Raises
    ------
    InsufficientDataError
        If there are fewer observations than the span requires.

    References
    ----------
    Montgomery (2019), 8th ed., §6.4.
    """
    if span < MIN_MOVING_RANGE_OBSERVATIONS:
        raise InsufficientDataError(
            "a moving range spans at least two observations",
            span=span,
            required=MIN_MOVING_RANGE_OBSERVATIONS,
        )
    if values.size < span:
        raise InsufficientDataError(
            "too few observations to form a moving range",
            n=int(values.size),
            required=span,
        )
    windows = np.lib.stride_tricks.sliding_window_view(values, span)
    spans: FloatArray = np.ptp(windows, axis=-1)
    return spans


def subgroup_ranges(subgroups: FloatMatrix) -> FloatArray:
    """Range of each subgroup, one row at a time.

    Parameters
    ----------
    subgroups
        Two-dimensional, one row per subgroup, equal sizes.

    Returns
    -------
    FloatArray
        One range per row.

    Raises
    ------
    InsufficientDataError
        If the subgroups hold fewer than two observations each.
    """
    _require_subgroup_shape(subgroups)
    ranges: FloatArray = np.ptp(subgroups, axis=1)
    return ranges


def subgroup_stdevs(subgroups: FloatMatrix) -> FloatArray:
    """Sample standard deviation of each subgroup, with ``n - 1`` in the denominator.

    Parameters
    ----------
    subgroups
        Two-dimensional, one row per subgroup, equal sizes.

    Returns
    -------
    FloatArray
        One standard deviation per row.

    Raises
    ------
    InsufficientDataError
        If the subgroups hold fewer than two observations each.
    """
    _require_subgroup_shape(subgroups)
    deviations: FloatArray = np.std(subgroups, axis=1, ddof=1)
    return deviations


def sigma_within_moving_range(
    values: FloatArray,
    span: int = MOVING_RANGE_SPAN,
) -> SigmaEstimate:
    r"""Short-term sigma for individuals, as :math:`\overline{MR} / d_2`.

    Parameters
    ----------
    values
        Individual observations in time order, in the measurement's own unit.
    span
        Moving range span; two unless there is a documented reason otherwise.

    Returns
    -------
    SigmaEstimate
        Tagged ``SigmaEstimator.MR_BAR_D2``.

    Raises
    ------
    InsufficientDataError
        If there are too few observations to form a moving range.
    DegenerateSeriesError
        If every observation is identical, which gives a zero estimate and
        therefore zero-width limits that would signal on every subsequent
        point.

    References
    ----------
    Montgomery (2019), 8th ed., §6.4, Equation 6.24.
    NIST/SEMATECH e-Handbook, §6.3.2.
    """
    ranges = moving_ranges(values, span)
    mean_range = float(np.mean(ranges))
    _reject_zero_dispersion(mean_range, "mean moving range", int(values.size))
    return SigmaEstimate(
        value=mean_range / d2(span),
        estimator=SigmaEstimator.MR_BAR_D2,
        subgroup_size=span,
        n_subgroups=int(ranges.size),
    )


def sigma_within_range(subgroups: FloatMatrix) -> SigmaEstimate:
    r"""Short-term sigma from subgroup ranges, as :math:`\bar{R} / d_2`.

    The classical estimator behind the X-bar/R chart. Efficient enough for the
    subgroup sizes fabs use, and less efficient than
    :func:`sigma_within_stdev` above roughly n = 10, which is why Montgomery
    recommends switching there.

    Parameters
    ----------
    subgroups
        Two-dimensional, one row per subgroup, equal sizes.

    Returns
    -------
    SigmaEstimate
        Tagged ``SigmaEstimator.R_BAR_D2``.

    Raises
    ------
    InsufficientDataError
        If the subgroups hold fewer than two observations each.
    DegenerateSeriesError
        If every subgroup range is zero.

    References
    ----------
    Montgomery (2019), 8th ed., §6.2.1, Equation 6.5.
    """
    ranges = subgroup_ranges(subgroups)
    mean_range = float(np.mean(ranges))
    _reject_zero_dispersion(mean_range, "mean subgroup range", int(subgroups.size))
    subgroup_size = int(subgroups.shape[1])
    return SigmaEstimate(
        value=mean_range / d2(subgroup_size),
        estimator=SigmaEstimator.R_BAR_D2,
        subgroup_size=subgroup_size,
        n_subgroups=int(subgroups.shape[0]),
    )


def sigma_within_stdev(subgroups: FloatMatrix) -> SigmaEstimate:
    r"""Short-term sigma from subgroup standard deviations, as :math:`\bar{s} / c_4`.

    The division by :math:`c_4` is not optional polish. The mean of the
    subgroup standard deviations underestimates sigma by 6% at n = 5 and 3% at
    n = 10, and an uncorrected estimate produces limits that are too narrow by
    the same fraction.

    Parameters
    ----------
    subgroups
        Two-dimensional, one row per subgroup, equal sizes.

    Returns
    -------
    SigmaEstimate
        Tagged ``SigmaEstimator.S_BAR_C4``.

    Raises
    ------
    InsufficientDataError
        If the subgroups hold fewer than two observations each.
    DegenerateSeriesError
        If every subgroup standard deviation is zero.

    References
    ----------
    Montgomery (2019), 8th ed., §6.3.1, Equation 6.24.
    """
    deviations = subgroup_stdevs(subgroups)
    mean_stdev = float(np.mean(deviations))
    _reject_zero_dispersion(mean_stdev, "mean subgroup standard deviation", int(subgroups.size))
    subgroup_size = int(subgroups.shape[1])
    return SigmaEstimate(
        value=mean_stdev / c4(subgroup_size),
        estimator=SigmaEstimator.S_BAR_C4,
        subgroup_size=subgroup_size,
        n_subgroups=int(subgroups.shape[0]),
    )


def sigma_overall(values: FloatArray, *, bias_corrected: bool = False) -> SigmaEstimate:
    r"""Long-term sigma: the sample standard deviation of everything.

    Includes between-subgroup movement, so it answers "what did the customer
    actually receive" rather than "how repeatable is this process over a few
    units". Used for Pp and Ppk, never for control limits.

    Parameters
    ----------
    values
        Every observation in the window, in any order — the statistic is
        order-independent, which is precisely why it cannot see drift.
    bias_corrected
        Divide by :math:`c_4(N)` to remove the downward bias of the sample
        standard deviation. Off by default because Montgomery's Pp and Ppk are
        defined on the uncorrected statistic, and the correction is under 0.3%
        beyond N = 100. Turn it on only where the reference being reproduced
        applies it.

    Returns
    -------
    SigmaEstimate
        Tagged ``SigmaEstimator.SAMPLE_STD``.

    Raises
    ------
    InsufficientDataError
        If fewer than two observations are supplied.
    DegenerateSeriesError
        If every observation is identical.

    References
    ----------
    Montgomery (2019), 8th ed., §8.3.
    NIST/SEMATECH e-Handbook, §6.1.6.
    """
    count = int(values.size)
    if count < MIN_SUBGROUP_SIZE:
        raise InsufficientDataError(
            "a standard deviation needs at least two observations",
            n=count,
            required=MIN_SUBGROUP_SIZE,
        )
    deviation = float(np.std(values, ddof=1))
    _reject_zero_dispersion(deviation, "sample standard deviation", count)
    if bias_corrected:
        # Above the largest tabulated size the correction is under 1% and still
        # shrinking, so clamping moves the fourth decimal place at worst —
        # whereas refusing would disable the option on the long records it is
        # for.
        deviation /= c4(min(count, MAX_TABULATED_SUBGROUP_SIZE))
    return SigmaEstimate(
        value=deviation,
        estimator=SigmaEstimator.SAMPLE_STD,
        subgroup_size=count,
        n_subgroups=1,
    )


def _require_subgroup_shape(subgroups: FloatMatrix) -> None:
    """Reject anything that is not a rectangle of at least two columns.

    Raises
    ------
    InsufficientDataError
        If the array is not two-dimensional, has no rows, or has columns below
        the minimum subgroup size.
    """
    if subgroups.ndim != _SUBGROUP_AXES:
        raise InsufficientDataError(
            "subgroups must form a two-dimensional array, one row per subgroup",
            shape=subgroups.shape,
        )
    rows, columns = subgroups.shape
    if rows < 1:
        raise InsufficientDataError("no subgroups supplied", n=rows, required=1)
    if columns < MIN_SUBGROUP_SIZE:
        raise InsufficientDataError(
            "a subgroup needs at least two observations to have a range",
            subgroup_size=columns,
            required=MIN_SUBGROUP_SIZE,
        )


def _reject_zero_dispersion(estimate: float, description: str, count: int) -> None:
    """Refuse a zero dispersion estimate rather than return zero-width limits.

    A constant series is not a perfect process; it is almost always a stuck
    sensor, a placeholder value, or a unit-conversion failure that rounded
    everything to the same number. Returning zero here would produce limits of
    zero width, and every subsequent point would violate them.

    Raises
    ------
    DegenerateSeriesError
        If the estimate is zero or negative.
    """
    if estimate <= 0.0:
        raise DegenerateSeriesError(
            f"{description} is zero, so no dispersion can be estimated",
            n=count,
            estimate=estimate,
        )
