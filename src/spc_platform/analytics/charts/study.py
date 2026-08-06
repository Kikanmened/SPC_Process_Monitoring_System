"""Phase I: estimating limits from a set of subgroups.

A control chart is used in two quite different ways, and conflating them is the
oldest mistake in the subject. Phase I asks "was this process stable, and if so
what are its limits" of a set of data already in hand. Phase II asks "is this
new point consistent with the process we established" against limits fixed
beforehand.

This module does Phase I only. It returns numbers, not a chart. Nothing here
can draw a point against limits computed from that same point, because nothing
here draws anything — that lives in the chart builders, and they require a
``Baseline`` (FR-C03). Published worked examples are Phase I studies, which is
why this module is what the reference tests exercise.
"""

from __future__ import annotations

from dataclasses import dataclass

from spc_platform.analytics.estimators.sigma import SigmaEstimate
from spc_platform.domain.enums import ChartStatistic, ChartType


@dataclass(frozen=True, slots=True)
class PanelEstimate:
    """Estimated centre line and limits for one panel.

    Attributes
    ----------
    statistic
        What the panel plots.
    centre_line
        Estimated centre.
    lcl, ucl
        Estimated limits, already clipped at the statistic's floor where it
        has one.
    sigma_statistic
        Standard error of one plotted point, which sets the zone width.
    has_lower_limit
        False when the lower limit was clipped to the statistic's floor and
        therefore cannot be crossed. On an R chart below n = 7 this is the
        normal case, and a chart that draws an LCL of zero as if it were a real
        boundary invites someone to read a run of small ranges as a violation.
    """

    statistic: ChartStatistic
    centre_line: float
    lcl: float
    ucl: float
    sigma_statistic: float
    has_lower_limit: bool = True


@dataclass(frozen=True, slots=True)
class ChartStudy:
    """The result of a Phase I study: what the limits would be, and from what.

    Attributes
    ----------
    chart_type
        Family studied.
    location
        The panel tracking the process centre.
    dispersion
        The panel tracking spread, absent for charts that have only one panel.
    sigma_within
        The short-term sigma estimate the limits rest on, carrying the name of
        the estimator that produced it.
    n_subgroups
        Subgroups the study covers.
    subgroup_size
        Observations per subgroup, or the moving range span for individuals.
    """

    chart_type: ChartType
    location: PanelEstimate
    sigma_within: SigmaEstimate
    n_subgroups: int
    subgroup_size: int
    dispersion: PanelEstimate | None = None

    @property
    def panels(self) -> tuple[PanelEstimate, ...]:
        """Every estimated panel, location first."""
        if self.dispersion is None:
            return (self.location,)
        return (self.location, self.dispersion)
