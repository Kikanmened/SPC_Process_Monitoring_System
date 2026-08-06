r"""Attribute charts: p, np, c, and u (FR-C01).

These count things instead of measuring them, and that changes one thing
fundamentally. On a variables chart the centre line and the spread are estimated
separately, so the chart can tell a shift in level from a change in variation.
On an attribute chart it cannot: under the binomial, :math:`\sigma` is
:math:`\sqrt{p(1-p)/n}`, a function of the centre line alone. There is nothing
left to estimate and nothing to compare the level against independently.

Two consequences follow, and both bite hardest in a fab.

**Limits move when the sample size does.** Inspect 50 units at one point and
500 at the next, and the second point's limits are three times tighter. Drawing
both against the average sample size — which is what a chart drawn by hand
usually does — makes the large samples look stable when they are not and the
small ones look wild when they are fine. Limits here are computed per point,
always.

**Real count data is usually wider than the distribution says.** Defects on a
wafer cluster; wafers within a lot share a process excursion; lots share a
consumable. The binomial and the Poisson both assume independence between the
units counted, and when that fails the theoretical limits are far too tight and
the chart signals on nearly every point. This is the single most common reason
an attribute chart gets switched off in production. So every study here reports
the observed-to-theoretical dispersion ratio, and can apply Laney's correction
on request — but it does not apply it silently, because a chart whose limits
were widened to stop it complaining is a different claim from one whose limits
came from the distribution.

References
----------
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §7.2 (p and np), §7.3 (c and u).
Laney, D. B. (2002). "Improved Control Charts for Attributes." *Quality
Engineering* 14(4), 531-537.
NIST/SEMATECH e-Handbook of Statistical Methods, §6.3.3.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

import numpy as np

from spc_platform.analytics.charts.panels import (
    LimitBasis,
    PanelIdentity,
    PlottedPoints,
    build_panel,
)
from spc_platform.analytics.estimators.constants import d2
from spc_platform.common.errors import (
    ConfigurationError,
    DegenerateSeriesError,
    InsufficientDataError,
    UnsupportedChartError,
)
from spc_platform.common.types import FloatArray, IntArray
from spc_platform.domain.charting import ChartPanel
from spc_platform.domain.enums import ChartStatistic, ChartType, SigmaEstimator

MIN_ATTRIBUTE_POINTS = 2
"""A rate estimated from one sample is that sample, and its chart proves nothing."""

MOVING_RANGE_SPAN = 2
"""Consecutive differences, for the dispersion ratio's within-point estimate."""

OVERDISPERSION_THRESHOLD = 1.2
"""Above this the theoretical limits are too tight to be usable as drawn.

Laney's own guidance is that a ratio near one means the assumed distribution
holds and the classical chart is correct. Twenty percent excess is where the
limits are wrong by enough to change which points signal.
"""

UNDERDISPERSION_THRESHOLD = 0.75
"""Below this the data is *less* variable than the distribution allows.

Almost always a sign that the counts are not what they claim to be — rounded,
capped, averaged, or reported by someone who knows what the limits are. Worth
flagging for the same reason as overdispersion, and for a more troubling one.
"""


@dataclass(frozen=True, slots=True)
class AttributeCounts:
    """What was counted, out of how much, and when.

    Attributes
    ----------
    events
        Defective units, for p and np; defects, for c and u. Never negative,
        and for p and np never more than the opportunity.
    opportunity
        Units inspected at each point, for p and np. Inspection units — which
        need not be whole — for u. Ignored for c, which assumes a constant area
        of opportunity and is refused when that assumption is not met.
    timestamps
        When each point was produced, one per point.
    """

    events: IntArray
    opportunity: FloatArray
    timestamps: tuple[datetime, ...]


@dataclass(frozen=True, slots=True)
class AttributeDesign:
    """How wide to draw the limits, and whether to widen them for overdispersion.

    Attributes
    ----------
    sigma_multiplier
        Limit width in standard errors, conventionally three.
    laney_correction
        Scale the standard errors by the observed dispersion ratio, giving
        Laney's p' or u' chart. Off by default: applying it turns a chart that
        says "this process is not binomial" into one that says nothing, and
        that should be a decision somebody makes rather than a default.
    """

    sigma_multiplier: float = 3.0
    laney_correction: bool = False


DEFAULT_ATTRIBUTE_DESIGN = AttributeDesign()
"""Three sigma limits, straight from the assumed distribution."""


@dataclass(frozen=True, slots=True)
class DispersionCheck:
    r"""Whether the counts behave the way the assumed distribution requires.

    Attributes
    ----------
    ratio
        Laney's :math:`\sigma_z`: the standard deviation of the standardised
        points, estimated from their moving ranges so that a genuine shift in
        level does not inflate it. One means the data is exactly as variable as
        the binomial or Poisson predicts.
    is_overdispersed
        The counts vary more than the distribution allows, so the theoretical
        limits are too tight and the chart will over-signal.
    is_underdispersed
        The counts vary less than the distribution allows. Rarely a real
        process; usually an artefact of how the data was recorded.
    applied
        Whether the ratio was used to widen the limits.

    Notes
    -----
    The moving range estimator is the point of the method. Taking the plain
    standard deviation of the standardised points would count a real process
    shift as extra dispersion and widen the limits until the shift no longer
    signalled, which is precisely the failure the chart exists to prevent.
    """

    ratio: float
    is_overdispersed: bool
    is_underdispersed: bool
    applied: bool


@dataclass(frozen=True, slots=True)
class AttributeStudy:
    """A fitted attribute chart and the rate its centre line came from.

    Attributes
    ----------
    panel
        The plotted rate or count with its per-point limits.
    centre_line
        The pooled rate: p-bar, n p-bar, c-bar, or u-bar.
    total_events
        Defectives or defects summed over every point.
    total_opportunity
        Units or inspection units summed over every point.
    dispersion
        Whether the counts behave the way the assumed distribution requires.
    """

    panel: ChartPanel
    centre_line: float
    total_events: int
    total_opportunity: float
    dispersion: DispersionCheck


def p_study(
    counts: AttributeCounts,
    identity: PanelIdentity,
    design: AttributeDesign = DEFAULT_ATTRIBUTE_DESIGN,
) -> AttributeStudy:
    r"""Chart the fraction defective, with limits that follow the sample size.

    .. math::
        \bar{p} = \frac{\sum d_i}{\sum n_i}, \qquad
        \sigma_i = \sqrt{\frac{\bar{p}(1 - \bar{p})}{n_i}}

    The pooled rate is the total over the total, not the average of the
    per-point rates. The two differ whenever the sample sizes differ, and the
    average of the rates gives every point equal weight regardless of how much
    was inspected — which is how a lot with 5 units inspected ends up moving the
    centre line as much as one with 5000.

    Parameters
    ----------
    counts
        Defective units and units inspected at each point.
    identity
        Parameter, baseline, and unit. Chart type and statistic are set here.
    design
        Limit width and whether to correct for overdispersion.

    Returns
    -------
    AttributeStudy
        The chart, the pooled rate, and the dispersion check.

    Raises
    ------
    InsufficientDataError
        If there are fewer than two points, or the arrays disagree in length.
    DegenerateSeriesError
        If nothing was found defective, or everything was, leaving no spread
        for the limits to be built from.
    ConfigurationError
        If any count is negative or exceeds the units inspected.

    References
    ----------
    Montgomery (2019), 8th ed., §7.2. Laney (2002), *Quality Engineering* 14(4).
    """
    _require_counts(counts, bounded=True)
    total_events = int(np.sum(counts.events))
    total_units = float(np.sum(counts.opportunity))
    rate = total_events / total_units
    _require_spread(rate, ceiling=1.0)

    spread = np.sqrt(rate * (1.0 - rate) / counts.opportunity)
    plotted = counts.events / counts.opportunity
    return _assemble(
        counts,
        identity,
        design,
        _Fit(
            chart_type=ChartType.P,
            statistic=ChartStatistic.PROPORTION_DEFECTIVE,
            centre_line=rate,
            spread=spread,
            plotted=plotted,
            estimator=SigmaEstimator.BINOMIAL,
            floor=0.0,
            ceiling=1.0,
        ),
    )


def np_study(
    counts: AttributeCounts,
    identity: PanelIdentity,
    design: AttributeDesign = DEFAULT_ATTRIBUTE_DESIGN,
) -> AttributeStudy:
    r"""Chart the number defective, which requires a constant sample size.

    .. math::
        n\bar{p} \pm L\sqrt{n\bar{p}(1 - \bar{p})}

    An np chart plots a count, so a count of 12 has to mean the same thing at
    every point. If the sample size varies it does not, and the chart is
    refused rather than silently rescaled — the p chart is the answer to that
    question and it is one call away.

    Parameters
    ----------
    counts
        Defective units and units inspected at each point.
    identity
        Parameter, baseline, and unit.
    design
        Limit width and whether to correct for overdispersion.

    Returns
    -------
    AttributeStudy
        The chart, the expected count, and the dispersion check.

    Raises
    ------
    UnsupportedChartError
        If the sample size is not the same at every point.
    InsufficientDataError
        If there are fewer than two points, or the arrays disagree in length.
    DegenerateSeriesError
        If nothing or everything was found defective.
    ConfigurationError
        If any count is negative or exceeds the units inspected.

    References
    ----------
    Montgomery (2019), 8th ed., §7.2.3.
    """
    _require_counts(counts, bounded=True)
    sizes = np.unique(counts.opportunity)
    if sizes.size != 1:
        raise UnsupportedChartError(
            "an np chart plots a raw count, which only compares across points "
            "when the sample size is constant; use a p chart instead",
            distinct_sizes=int(sizes.size),
            smallest=float(sizes.min()),
            largest=float(sizes.max()),
        )
    size = float(sizes[0])

    total_events = int(np.sum(counts.events))
    total_units = float(np.sum(counts.opportunity))
    rate = total_events / total_units
    _require_spread(rate, ceiling=1.0)

    expected = size * rate
    spread = np.array([np.sqrt(expected * (1.0 - rate))])
    return _assemble(
        counts,
        identity,
        design,
        _Fit(
            chart_type=ChartType.NP,
            statistic=ChartStatistic.COUNT_DEFECTIVE,
            centre_line=expected,
            spread=spread,
            plotted=counts.events.astype(np.float64),
            estimator=SigmaEstimator.BINOMIAL,
            floor=0.0,
            ceiling=size,
        ),
    )


def c_study(
    counts: AttributeCounts,
    identity: PanelIdentity,
    design: AttributeDesign = DEFAULT_ATTRIBUTE_DESIGN,
) -> AttributeStudy:
    r"""Chart the count of defects over a constant area of opportunity.

    .. math::
        \bar{c} \pm L\sqrt{\bar{c}}

    The Poisson has one parameter, so the centre line fixes the limits
    completely. That is the whole chart, and it is also why it fails loudly on
    clustered defects: the variance of a clustered count exceeds its mean, often
    by a lot, and the dispersion check is the only warning of it.

    Parameters
    ----------
    counts
        Defects at each point. The opportunity must be constant, since a count
        compared against a fixed limit has to be a count of the same thing.
    identity
        Parameter, baseline, and unit.
    design
        Limit width and whether to correct for overdispersion.

    Returns
    -------
    AttributeStudy
        The chart, the mean count, and the dispersion check.

    Raises
    ------
    UnsupportedChartError
        If the area of opportunity is not the same at every point.
    InsufficientDataError
        If there are fewer than two points, or the arrays disagree in length.
    DegenerateSeriesError
        If no defects were found at all.
    ConfigurationError
        If any count is negative.

    References
    ----------
    Montgomery (2019), 8th ed., §7.3.1.
    """
    _require_counts(counts, bounded=False)
    if np.unique(counts.opportunity).size != 1:
        raise UnsupportedChartError(
            "a c chart counts defects over a constant area of opportunity; "
            "use a u chart when the inspected amount varies",
            distinct_opportunities=int(np.unique(counts.opportunity).size),
        )

    total_events = int(np.sum(counts.events))
    mean_count = total_events / counts.events.size
    _require_spread(mean_count, ceiling=None)

    return _assemble(
        counts,
        identity,
        design,
        _Fit(
            chart_type=ChartType.C,
            statistic=ChartStatistic.COUNT_DEFECTS,
            centre_line=mean_count,
            spread=np.array([np.sqrt(mean_count)]),
            plotted=counts.events.astype(np.float64),
            estimator=SigmaEstimator.POISSON,
            floor=0.0,
            ceiling=None,
        ),
    )


def u_study(
    counts: AttributeCounts,
    identity: PanelIdentity,
    design: AttributeDesign = DEFAULT_ATTRIBUTE_DESIGN,
) -> AttributeStudy:
    r"""Chart defects per unit, with limits that follow the amount inspected.

    .. math::
        \bar{u} = \frac{\sum c_i}{\sum n_i}, \qquad
        \sigma_i = \sqrt{\frac{\bar{u}}{n_i}}

    The u chart is the c chart's answer to a varying inspection size, and the
    inspection size need not be a whole number: half a wafer inspected is half
    an inspection unit, and the limits widen accordingly.

    Parameters
    ----------
    counts
        Defects found and inspection units examined at each point.
    identity
        Parameter, baseline, and unit.
    design
        Limit width and whether to correct for overdispersion.

    Returns
    -------
    AttributeStudy
        The chart, the mean defects per unit, and the dispersion check.

    Raises
    ------
    InsufficientDataError
        If there are fewer than two points, or the arrays disagree in length.
    DegenerateSeriesError
        If no defects were found at all.
    ConfigurationError
        If any count is negative, or any inspection size is not positive.

    References
    ----------
    Montgomery (2019), 8th ed., §7.3.2.
    """
    _require_counts(counts, bounded=False)
    total_events = int(np.sum(counts.events))
    total_units = float(np.sum(counts.opportunity))
    rate = total_events / total_units
    _require_spread(rate, ceiling=None)

    return _assemble(
        counts,
        identity,
        design,
        _Fit(
            chart_type=ChartType.U,
            statistic=ChartStatistic.DEFECTS_PER_UNIT,
            centre_line=rate,
            spread=np.sqrt(rate / counts.opportunity),
            plotted=counts.events / counts.opportunity,
            estimator=SigmaEstimator.POISSON,
            floor=0.0,
            ceiling=None,
        ),
    )


def dispersion_ratio(plotted: FloatArray, centre_line: float, spread: FloatArray) -> float:
    r"""Measure how much wider the counts are than the assumed distribution allows.

    Standardise each point by its own theoretical standard error, then estimate
    the standard deviation of those standardised values from their mean moving
    range. If the distribution holds, the standardised values are standard
    normal and the ratio is one.

    The moving range is what makes this usable. A plain standard deviation of
    the standardised points would absorb any real shift in level into the
    dispersion estimate and widen the limits until the shift stopped signalling.
    Consecutive differences see only the point-to-point variation, so a
    sustained shift contributes almost nothing.

    Parameters
    ----------
    plotted
        The plotted statistic at each point.
    centre_line
        The pooled rate.
    spread
        Theoretical standard error at each point, or one value if constant.

    Returns
    -------
    float
        Laney's :math:`\sigma_z`. One means the distribution fits.

    References
    ----------
    Laney (2002), *Quality Engineering* 14(4), 531-537.
    """
    standardised = (plotted - centre_line) / spread
    ranges = np.abs(np.diff(standardised))
    return float(np.mean(ranges) / d2(MOVING_RANGE_SPAN))


@dataclass(frozen=True, slots=True)
class _Fit:
    """The distribution-specific part of an attribute chart, before assembly."""

    chart_type: ChartType
    statistic: ChartStatistic
    centre_line: float
    spread: FloatArray
    plotted: FloatArray
    estimator: SigmaEstimator
    floor: float | None
    ceiling: float | None


def _assemble(
    counts: AttributeCounts,
    identity: PanelIdentity,
    design: AttributeDesign,
    fit: _Fit,
) -> AttributeStudy:
    """Check dispersion, optionally widen the limits, and build the panel.

    The dispersion check runs on the uncorrected standard errors regardless of
    whether the correction is applied, so the reported ratio always answers the
    same question: does the assumed distribution fit this data.
    """
    check = _check_dispersion(fit, design)
    spread = fit.spread * check.ratio if check.applied else fit.spread
    estimator = SigmaEstimator.LANEY if check.applied else fit.estimator

    panel = build_panel(
        replace(identity, chart_type=fit.chart_type, statistic=fit.statistic),
        PlottedPoints(
            values=fit.plotted,
            timestamps=counts.timestamps,
            subgroup_sizes=tuple(round(size) for size in counts.opportunity),
        ),
        LimitBasis(
            centre_line=fit.centre_line,
            sigma_statistic=spread,
            sigma_process=float(np.mean(spread)),
            sigma_multiplier=design.sigma_multiplier,
            sigma_estimator=estimator,
            floor=fit.floor,
            ceiling=fit.ceiling,
        ),
    )
    return AttributeStudy(
        panel=panel,
        centre_line=fit.centre_line,
        total_events=int(np.sum(counts.events)),
        total_opportunity=float(np.sum(counts.opportunity)),
        dispersion=check,
    )


def _check_dispersion(fit: _Fit, design: AttributeDesign) -> DispersionCheck:
    """Compare the observed point-to-point variation against the theoretical one."""
    ratio = dispersion_ratio(fit.plotted, fit.centre_line, fit.spread)
    return DispersionCheck(
        ratio=ratio,
        is_overdispersed=ratio > OVERDISPERSION_THRESHOLD,
        is_underdispersed=ratio < UNDERDISPERSION_THRESHOLD,
        applied=design.laney_correction and ratio > 0.0,
    )


def _require_counts(counts: AttributeCounts, *, bounded: bool) -> None:
    """Refuse counts that cannot have come from the process they claim to describe.

    Parameters
    ----------
    counts
        What was counted, out of how much.
    bounded
        Whether an event count is capped by the opportunity. True for
        defective *units*, which cannot outnumber the units inspected; false
        for *defects*, of which one unit can carry many.

    Raises
    ------
    InsufficientDataError
        If there are too few points, or the arrays disagree in length.
    ConfigurationError
        If a count is negative, an opportunity is not positive, or a bounded
        count exceeds its opportunity.
    """
    points = int(counts.events.size)
    if points < MIN_ATTRIBUTE_POINTS:
        raise InsufficientDataError(
            "an attribute chart needs at least two points to estimate a rate",
            n=points,
            required=MIN_ATTRIBUTE_POINTS,
        )
    if counts.opportunity.size != points or len(counts.timestamps) != points:
        raise InsufficientDataError(
            "counts, opportunities, and timestamps must line up point for point",
            events=points,
            opportunity=int(counts.opportunity.size),
            timestamps=len(counts.timestamps),
        )
    if np.any(counts.events < 0):
        raise ConfigurationError(
            "a count of defects or defectives cannot be negative",
            smallest=int(np.min(counts.events)),
        )
    if np.any(counts.opportunity <= 0.0):
        raise ConfigurationError(
            "every point must have inspected something",
            smallest=float(np.min(counts.opportunity)),
        )
    if bounded and np.any(counts.events > counts.opportunity):
        raise ConfigurationError(
            "more units were found defective than were inspected",
            worst=int(np.max(counts.events - counts.opportunity)),
        )


def _require_spread(rate: float, *, ceiling: float | None) -> None:
    """Refuse a rate at the edge of its range, where the limits collapse.

    A process with no defectives at all has a standard error of zero and limits
    of zero width, which would make the next defective an infinitely strong
    signal. It is a real and common situation, and the honest answer is that a
    control chart is not the tool for it.

    Raises
    ------
    DegenerateSeriesError
        If the rate is zero, or sits at its upper bound.
    """
    if rate <= 0.0:
        raise DegenerateSeriesError(
            "nothing was found defective, so the chart has no spread to draw; "
            "a rare-event chart is the tool for this data",
            rate=rate,
        )
    if ceiling is not None and rate >= ceiling:
        raise DegenerateSeriesError(
            "everything was found defective, so the chart has no spread to draw",
            rate=rate,
            ceiling=ceiling,
        )
