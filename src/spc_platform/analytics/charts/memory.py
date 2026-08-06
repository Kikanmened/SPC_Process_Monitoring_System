r"""EWMA and CUSUM: charts that remember (FR-C01).

A Shewhart chart judges each point alone. That makes it excellent at catching a
large sudden shift and nearly blind to a small sustained one: a drift of one
sigma takes an average of 44 subgroups to cross a three sigma limit, by which
time a fab has run several lots through the excursion. The charts here fix that
by carrying information forward, which is exactly the property that makes them
worth having and the property that makes them easy to misuse.

Three consequences follow, and all three are enforced below rather than left to
the caller.

**These are Phase II charts.** Both are defined relative to an established
target and a known sigma. Estimating those from the same data the chart then
judges produces a chart that cannot signal on the excursion it was estimated
from, and the failure is silent. So both functions take a target and a sigma;
neither derives them.

**Their parameters are not independent.** An EWMA with :math:`\lambda = 0.2` and
:math:`L = 3` has an in-control ARL near 500; the same :math:`\lambda` with
:math:`L = 2.7` gives about 350. A CUSUM with :math:`k = 0.5` and :math:`h = 5`
gives 465, and :math:`h = 4` gives 168. Changing one number without the other
changes the false alarm rate by a factor nobody notices until the chart is
either ignored or trusted when it should not be. Each scheme's parameters are
therefore a single object with a documented ARL, not loose arguments.

**Run rules do not belong on them.** The zone rules assume independent points.
EWMA statistics are correlated by construction — that is what the memory is —
and CUSUM values are cumulative, so a run of eight on one side of a CUSUM
centre line means nothing at all. Both charts signal by their own limits, and
the rule catalogue is not applied to them.

References
----------
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §9.1 (CUSUM), §9.2 (EWMA), Tables 9.3 and 9.11 for ARLs.
Roberts, S. W. (1959). "Control Chart Tests Based on Geometric Moving
Averages." *Technometrics* 1(3), 239-250.
Page, E. S. (1954). "Continuous Inspection Schemes." *Biometrika* 41(1), 100-115.
Lucas, J. M. and Saccucci, M. S. (1990). "Exponentially Weighted Moving Average
Control Schemes: Properties and Enhancements." *Technometrics* 32(1), 1-12.
NIST/SEMATECH e-Handbook of Statistical Methods, §6.3.2.4 (CUSUM), §6.3.2.5
(EWMA).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from spc_platform.analytics.charts.panels import (
    LimitBasis,
    PanelIdentity,
    PlottedPoints,
    build_panel,
)
from spc_platform.common.errors import ConfigurationError, InsufficientDataError
from spc_platform.common.types import FloatArray
from spc_platform.domain.charting import ChartPanel, ControlChart
from spc_platform.domain.enums import ChartStatistic, ChartType, SigmaEstimator

MIN_MEMORY_OBSERVATIONS = 2
"""A chart that remembers needs something to remember."""


@dataclass(frozen=True, slots=True)
class MemoryChartSettings:
    """Target and sigma a Phase II memory chart is judged against.

    Attributes
    ----------
    target
        The in-control process mean. Comes from a qualified baseline, never
        from the data being charted.
    sigma
        Standard deviation of one plotted observation, in measurement units.
        For subgroup means that is the standard error of the mean, not the
        process sigma — the two differ by the square root of the subgroup size,
        and using the wrong one moves the ARL by more than an order of
        magnitude.
    sigma_estimator
        Which estimator produced ``sigma``, carried onto the limits so a chart
        can state how it was drawn.
    """

    target: float
    sigma: float
    sigma_estimator: SigmaEstimator


@dataclass(frozen=True, slots=True)
class EwmaDesign:
    r"""The weight and the limit width, which only mean anything together.

    Attributes
    ----------
    weight
        :math:`\lambda`, the weight on each new observation, in ``(0, 1]``.
        Small values give a long memory and detect small shifts fast; a value
        of one is a Shewhart chart. Between 0.05 and 0.25 is the usual range.
    sigma_multiplier
        :math:`L`, the limit width in standard errors of the EWMA statistic.
    asymptotic_limits
        Use the steady-state width at every point instead of the exact
        time-varying width. Easier to read off a table and wrong for the first
        handful of points, so it is off by default.

    Notes
    -----
    The default pair, :math:`\lambda = 0.2` with :math:`L = 3`, has an
    in-control ARL of about 500 and detects a one sigma shift in about 10
    observations (Montgomery Table 9.11; Lucas and Saccucci 1990). Changing
    either number alone invalidates both figures.
    """

    weight: float = 0.2
    sigma_multiplier: float = 3.0
    asymptotic_limits: bool = False


@dataclass(frozen=True, slots=True)
class CusumDesign:
    r"""The reference value and decision interval, which are chosen as a pair.

    Attributes
    ----------
    slack
        :math:`k` in process sigmas — half the shift the scheme is tuned to
        detect. At 0.5 the chart is tuned for a one sigma shift.
    decision
        :math:`h` in process sigmas — the signalling threshold.

    Notes
    -----
    The default pair, :math:`(k, h) = (0.5, 5)`, has an in-control ARL of 465
    and detects a one sigma shift in about 10 observations. The pair
    :math:`(0.5, 4)` gives an in-control ARL of 168 instead, which is a
    different chart wearing the same name (Montgomery Table 9.3).
    """

    slack: float = 0.5
    decision: float = 5.0


DEFAULT_EWMA_DESIGN = EwmaDesign()
r"""Lambda 0.2 with L = 3: in-control ARL about 500, one sigma shift in about 10.

Safe to share, being frozen. Named so that a caller who takes the default is
taking a documented scheme rather than an accident of the signature.
"""

DEFAULT_CUSUM_DESIGN = CusumDesign()
r"""k = 0.5 with h = 5: in-control ARL 465, one sigma shift in about 10.

Montgomery Table 9.3. The comparable EWMA design above was chosen to match it,
which is what makes the two charts' published detection times comparable.
"""


def ewma_chart(
    points: PlottedPoints,
    identity: PanelIdentity,
    settings: MemoryChartSettings,
    design: EwmaDesign = DEFAULT_EWMA_DESIGN,
) -> ChartPanel:
    r"""Chart an exponentially weighted moving average against a fixed target.

    .. math::
        z_i = \lambda x_i + (1 - \lambda) z_{i-1}, \qquad z_0 = \mu_0

    The limits widen with :math:`i` and settle quickly:

    .. math::
        \mu_0 \pm L\sigma\sqrt{\frac{\lambda}{2-\lambda}
                               \left[1 - (1-\lambda)^{2i}\right]}

    The bracketed term is what stops the chart signalling on its own start-up.
    Early on, :math:`z` has barely moved from the target and its variance is far
    below the asymptotic value, so asymptotic limits are too wide there and the
    first few points are effectively unmonitored. Exact limits are the default
    for that reason.

    Parameters
    ----------
    points
        Observations in time order with their timestamps and subgroup sizes.
        The plotted values are replaced by the smoothed series; timestamps and
        sizes carry through unchanged.
    identity
        Parameter, baseline, chart type, statistic, and unit.
    settings
        Target and the standard deviation of one observation, from the
        baseline.
    design
        Weight, limit width, and whether to use asymptotic limits.

    Returns
    -------
    ChartPanel
        The smoothed series with its limits.

    Raises
    ------
    InsufficientDataError
        If there are fewer than two observations, or the timestamps do not
        match them one for one.
    ConfigurationError
        If the weight is outside ``(0, 1]``, or the sigma is not positive.

    References
    ----------
    Roberts (1959), *Technometrics* 1(3). Montgomery (2019), 8th ed., §9.2.
    Lucas and Saccucci (1990), *Technometrics* 32(1).
    """
    _require_series(points)
    _require_positive_sigma(settings)
    if not 0.0 < design.weight <= 1.0:
        raise ConfigurationError(
            "the EWMA weight must lie in (0, 1]",
            weight=design.weight,
        )

    smoothed = ewma(points.values, settings.target, design.weight)
    steady = settings.sigma * np.sqrt(design.weight / (2.0 - design.weight))
    if design.asymptotic_limits:
        spread = np.full(smoothed.size, steady, dtype=np.float64)
    else:
        index = np.arange(1, smoothed.size + 1, dtype=np.float64)
        spread = steady * np.sqrt(1.0 - (1.0 - design.weight) ** (2.0 * index))

    return build_panel(
        identity,
        replace(points, values=smoothed),
        LimitBasis(
            centre_line=settings.target,
            sigma_statistic=spread,
            sigma_process=settings.sigma,
            sigma_multiplier=design.sigma_multiplier,
            sigma_estimator=settings.sigma_estimator,
        ),
    )


def cusum_chart(
    points: PlottedPoints,
    identity: PanelIdentity,
    settings: MemoryChartSettings,
    design: CusumDesign = DEFAULT_CUSUM_DESIGN,
) -> ControlChart:
    r"""Chart the tabular CUSUM, upper and lower arms, against a fixed target.

    .. math::
        C_i^+ = \max\left[0,\; x_i - (\mu_0 + K) + C_{i-1}^+\right] \\
        C_i^- = \max\left[0,\; (\mu_0 - K) - x_i + C_{i-1}^-\right]

    Both arms are plotted in sigma units, so the decision interval is the same
    number on both and the chart reads the same whatever the measurement's unit.
    Both arms are non-negative and are compared against :math:`h` only from
    above — a lower control limit of zero would signal on a process behaving
    perfectly, which is why the lower arm is plotted as a magnitude rather than
    as a negative quantity.

    The two arms are returned as the location and dispersion panels of one
    chart. That is a slight abuse of those names, and the honest alternative to
    inventing a second container: both arms are location statistics, and the
    pairing records that they are read together.

    Parameters
    ----------
    points
        Observations in time order with their timestamps and subgroup sizes.
    identity
        Parameter, baseline, and unit. The chart type and statistic on
        ``identity`` are replaced; each arm names its own.
    settings
        Target and the standard deviation of one observation, from the
        baseline.
    design
        Reference value and decision interval.

    Returns
    -------
    ControlChart
        The upper arm as the location panel, the lower arm as its companion.

    Raises
    ------
    InsufficientDataError
        If there are fewer than two observations, or the timestamps do not
        match them one for one.
    ConfigurationError
        If the reference value or decision interval is not positive, or the
        sigma is not positive.

    References
    ----------
    Page (1954), *Biometrika* 41(1). Montgomery (2019), 8th ed., §9.1 and
    Table 9.3. NIST/SEMATECH e-Handbook, §6.3.2.4.
    """
    _require_series(points)
    _require_positive_sigma(settings)
    if design.slack <= 0.0 or design.decision <= 0.0:
        raise ConfigurationError(
            "the CUSUM reference value and decision interval must be positive",
            slack=design.slack,
            decision=design.decision,
        )

    deviations = (points.values - settings.target) / settings.sigma
    return ControlChart(
        location=_cusum_panel(
            points,
            identity,
            settings,
            _CusumArm(
                statistic=ChartStatistic.CUSUM_UPPER,
                values=_accumulate(deviations - design.slack),
            ),
            design.decision,
        ),
        dispersion=_cusum_panel(
            points,
            identity,
            settings,
            _CusumArm(
                statistic=ChartStatistic.CUSUM_LOWER,
                values=_accumulate(-deviations - design.slack),
            ),
            design.decision,
        ),
    )


def ewma(values: FloatArray, start: float, weight: float) -> FloatArray:
    r"""Smooth a series exponentially, starting from a given value.

    Written as an explicit loop. The recursion is first-order linear and has a
    closed form as a convolution, but that form loses precision for small
    :math:`\lambda` over long series because :math:`(1-\lambda)^{-i}` overflows
    while the running value it multiplies does not. At the lengths a fab charts
    the loop is not the bottleneck, and it is the version that stays correct.

    Parameters
    ----------
    values
        Observations in time order.
    start
        :math:`z_0`, conventionally the process target.
    weight
        :math:`\lambda`, the weight on each new observation.

    Returns
    -------
    FloatArray
        The smoothed series, the same length as ``values``.
    """
    smoothed = np.empty(values.size, dtype=np.float64)
    previous = start
    for position, value in enumerate(values):
        previous = weight * float(value) + (1.0 - weight) * previous
        smoothed[position] = previous
    return smoothed


def _accumulate(increments: FloatArray) -> FloatArray:
    """Run a cumulative sum that resets to zero whenever it would go negative.

    The reset is what makes a CUSUM a change detector rather than a random
    walk: without it, a long in-control stretch wanders arbitrarily far from
    zero and the decision interval stops meaning anything.
    """
    total = np.empty(increments.size, dtype=np.float64)
    running = 0.0
    for position, increment in enumerate(increments):
        running = max(0.0, running + float(increment))
        total[position] = running
    return total


@dataclass(frozen=True, slots=True)
class _CusumArm:
    """One side of the tabular CUSUM: which arm, and what it accumulated."""

    statistic: ChartStatistic
    values: FloatArray


def _cusum_panel(
    points: PlottedPoints,
    identity: PanelIdentity,
    settings: MemoryChartSettings,
    arm: _CusumArm,
    decision: float,
) -> ChartPanel:
    """Wrap one CUSUM arm as a panel with a one-sided decision interval.

    The arm is already in sigma units, so its standard error is one by
    construction and the decision interval is the sigma multiplier. The panel is
    one-sided: the arm signals only from above, and a lower limit at zero would
    fire on the most in-control reading the statistic has.
    """
    return build_panel(
        replace(identity, chart_type=ChartType.CUSUM, statistic=arm.statistic),
        replace(points, values=arm.values),
        LimitBasis(
            centre_line=0.0,
            sigma_statistic=np.array([1.0]),
            sigma_process=settings.sigma,
            sigma_multiplier=decision,
            sigma_estimator=settings.sigma_estimator,
            one_sided=True,
        ),
    )


def _require_series(points: PlottedPoints) -> None:
    """Refuse a series too short to remember anything, or one missing its clock.

    Raises
    ------
    InsufficientDataError
        If there are too few observations, or one timestamp per observation was
        not supplied.
    """
    count = int(points.values.size)
    if count < MIN_MEMORY_OBSERVATIONS:
        raise InsufficientDataError(
            "a chart that accumulates needs at least two observations",
            n=count,
            required=MIN_MEMORY_OBSERVATIONS,
        )
    if len(points.timestamps) != count:
        raise InsufficientDataError(
            "every observation needs a timestamp",
            n=count,
            timestamps=len(points.timestamps),
        )


def _require_positive_sigma(settings: MemoryChartSettings) -> None:
    """Refuse a sigma that would make every limit zero-width or inverted.

    Raises
    ------
    ConfigurationError
        If the baseline sigma is not positive.
    """
    if settings.sigma <= 0.0:
        raise ConfigurationError(
            "a memory chart needs a positive sigma from its baseline",
            sigma=settings.sigma,
            estimator=settings.sigma_estimator,
        )
