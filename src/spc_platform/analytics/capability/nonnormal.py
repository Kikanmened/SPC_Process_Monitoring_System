"""Capability for a process whose distribution is not normal (FR-P07).

The normal formula divides the specification width by six sigma. The general
form divides it by the distance between the 0.135th and 99.865th percentiles of
whatever distribution the process actually has, and centres on the median
rather than the mean. On a normal process the two agree, which is the property
that makes this the right generalisation rather than a different index wearing
the same name.

What it must never do is quietly stand in for the normal calculation. A Ppk of
1.4 computed this way and a Ppk of 1.4 computed the usual way are not the same
claim, and the difference is invisible once the number is in a report. So the
result carries its method, and a caller has to have chosen it.

References
----------
NIST/SEMATECH e-Handbook of Statistical Methods, §6.5.2.
Clements, J. A. (1989). "Process Capability Calculations for Non-Normal
Distributions." *Quality Progress* 22(9), 95-100.
ISO 22514-2:2017, "Statistical methods in process management — Capability and
performance", clause 8, for the percentile formulation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from spc_platform.analytics.capability.indices import (
    CapabilityContext,
    SpecificationSide,
    StabilityStatus,
    require_stability,
    side_of,
)
from spc_platform.analytics.distribution.normality import (
    CapabilityMethod,
    NaturalTolerance,
)
from spc_platform.common.errors import DegenerateSeriesError
from spc_platform.domain.specification_limit import SpecificationLimit


@dataclass(frozen=True, slots=True)
class NonNormalCapability:
    """Capability stated in percentiles rather than standard deviations.

    Attributes
    ----------
    parameter_id
        What was assessed.
    pp
        Specification width over the natural tolerance width. ``None`` for a
        single-sided specification.
    ppu, ppl
        Distance from the median to each limit, over the corresponding half of
        the natural tolerance. The two halves differ on a skewed process, which
        is the whole reason for computing it this way.
    ppk
        The worse of the two.
    tolerance
        The natural tolerance the indices were computed from.
    n_observations
        Sample size.
    window_start, window_end
        Period covered.
    stability
        Whether the process was demonstrated to be in control.
    specification_side
        Which limits existed.
    """

    parameter_id: str
    pp: float | None
    ppu: float | None
    ppl: float | None
    ppk: float
    tolerance: NaturalTolerance
    n_observations: int
    window_start: datetime
    window_end: datetime
    stability: StabilityStatus
    specification_side: SpecificationSide

    @property
    def method(self) -> CapabilityMethod:
        """How the distribution was handled."""
        return self.tolerance.method


def nonnormal_capability(
    tolerance: NaturalTolerance,
    specification: SpecificationLimit,
    *,
    n_observations: int,
    context: CapabilityContext,
) -> NonNormalCapability:
    """Compute capability from a natural tolerance rather than a sigma.

    The two halves of the natural tolerance are used separately. On a
    right-skewed process the upper half is the wider one, so the upper index
    falls faster than the lower as the median moves — which is what a skewed
    process does to the scrap rate, and what the symmetric formula hides.

    Parameters
    ----------
    tolerance
        Percentiles standing in for the three sigma points, from
        ``analytics.distribution.natural_tolerance``.
    specification
        The approved specification.
    n_observations
        Sample size behind the tolerance.
    context
        The window, the stability finding, and whether stability is required.

    Returns
    -------
    NonNormalCapability
        Indices with the method that produced them attached.

    Raises
    ------
    UnstableProcessError
        If the context requires stability and it was not demonstrated.
    DegenerateSeriesError
        If either half of the natural tolerance has zero width, which would
        make the corresponding index infinite.

    References
    ----------
    NIST/SEMATECH e-Handbook, §6.5.2. ISO 22514-2:2017, clause 8.
    """
    require_stability(specification, context)
    upper_half = tolerance.upper - tolerance.median
    lower_half = tolerance.median - tolerance.lower
    if upper_half <= 0.0 or lower_half <= 0.0:
        raise DegenerateSeriesError(
            "the natural tolerance has no width on one side of the median",
            upper_half=upper_half,
            lower_half=lower_half,
        )

    upper = (
        (specification.usl - tolerance.median) / upper_half
        if specification.usl is not None
        else None
    )
    lower = (
        (tolerance.median - specification.lsl) / lower_half
        if specification.lsl is not None
        else None
    )
    potential = (
        (specification.usl - specification.lsl) / tolerance.width
        if specification.usl is not None and specification.lsl is not None
        else None
    )
    # No further scaling: for a normal process the half natural tolerance is
    # exactly the three sigma distance, so these ratios already agree with the
    # normal Ppu and Ppl rather than differing from them by a constant.
    return NonNormalCapability(
        parameter_id=str(specification.parameter_id),
        pp=potential,
        ppu=upper,
        ppl=lower,
        ppk=min(value for value in (upper, lower) if value is not None),
        tolerance=tolerance,
        n_observations=n_observations,
        window_start=context.window[0],
        window_end=context.window[1],
        stability=context.stability,
        specification_side=side_of(specification),
    )
