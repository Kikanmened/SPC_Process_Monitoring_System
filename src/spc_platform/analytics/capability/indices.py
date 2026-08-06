"""Process capability: Cp, Cpk, Pp, Ppk, and Cpm.

A capability index is one number that a customer, an auditor, and a production
manager will each read differently, and the arithmetic is trivial. Everything
that makes it hard is in the conditions attached to it.

Three of those conditions are enforced by the types in this module rather than
by discipline.

**The estimator is never anonymous.** Cp and Cpk use short-term sigma, Pp and
Ppk use long-term. The same data yields both, and on a drifting process they
differ by a factor of two. Every result here carries the identity of the
estimator that produced it (FR-P03).

**Stability is a precondition, not a caveat.** Capability describes what a
process will do next, which is only meaningful if it is doing the same thing
now. A Cpk from an out-of-control process is not a pessimistic estimate or an
approximate one; it is a statement about a distribution that does not exist.
This module can refuse (FR-P04) and the application layer decides when to.

**A single-sided specification has no Cp.** There is no width to divide, and
returning half the two-sided formula silently doubles the reported capability.
The result records which side existed (FR-P08).

References
----------
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §8.2 (Cp, Cpk), §8.3 (Pp, Ppk, and the within/overall distinction),
§8.2.3 (Cpm).
NIST/SEMATECH e-Handbook of Statistical Methods, §6.1.6.
Chan, L. K., Cheng, S. W. and Spiring, F. A. (1988). "A New Measure of Process
Capability: Cpm." *Journal of Quality Technology* 20(3), 162-175.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

import numpy as np

from spc_platform.analytics.distribution.normality import NormalityAssessment
from spc_platform.analytics.estimators.sigma import SigmaEstimate
from spc_platform.common.errors import (
    DegenerateSeriesError,
    InsufficientDataError,
    UnstableProcessError,
)
from spc_platform.common.types import FloatArray
from spc_platform.domain.enums import SigmaEstimator
from spc_platform.domain.specification_limit import SpecificationLimit

CAPABILITY_SIGMA_SPAN = 6.0
"""The process width a capability index compares a specification against.

Three standard deviations either side of the mean, covering 99.73% of a normal
process. Cp of 1.0 therefore means the specification is exactly as wide as the
process, which sounds adequate and is not: it leaves nothing for the drift that
every real process has.
"""

HALF_SIGMA_SPAN = 3.0
"""One side of the process width, for the one-sided indices Cpu and Cpl."""

MIN_CAPABILITY_OBSERVATIONS = 2
"""Arithmetic minimum. The meaningful minimum is configured, and far larger.

Twenty-five to fifty subgroups is the usual requirement (FR-P05). This constant
only guards the division; it is the application's job to enforce a sample size
anybody would defend.
"""


class SpecificationSide(StrEnum):
    """Which specification limits a capability result was computed against."""

    BOTH = "both"
    UPPER_ONLY = "upper_only"
    LOWER_ONLY = "lower_only"


class StabilityStatus(StrEnum):
    """Whether the process was demonstrated to be in control (FR-P04, FR-P09)."""

    IN_CONTROL = "in_control"
    OUT_OF_CONTROL = "out_of_control"
    NOT_ASSESSED = "not_assessed"


@dataclass(frozen=True, slots=True)
class CapabilityIndices:
    """One family of indices, and the estimator they were all computed from.

    Attributes
    ----------
    cp
        Potential capability: how the specification width compares to the
        process width, ignoring where the process sits. ``None`` for a
        single-sided specification, which has no width.
    cpu, cpl
        Distance from the mean to each specification limit, in half process
        widths. ``None`` where that limit does not exist.
    cpk
        The worse of ``cpu`` and ``cpl`` — actual capability, which accounts
        for the process being off centre.
    estimator
        Which sigma produced these. Short-term gives Cp and Cpk; long-term
        gives Pp and Ppk. The names differ but the arithmetic does not, which
        is exactly why the estimator has to be recorded.
    sigma
        The dispersion estimate used.
    """

    cp: float | None
    cpu: float | None
    cpl: float | None
    cpk: float
    estimator: SigmaEstimator
    sigma: float


@dataclass(frozen=True, slots=True)
class DispersionPair:
    """The two sigmas a capability assessment needs, kept together.

    They are separate estimates of the same process and are only meaningful
    side by side: one alone gives a number with no scale to judge it against.
    Passing them as a pair also removes the chance of handing the long-term
    estimate to the short-term parameter, which would report a drifting process
    as a capable one.
    """

    within: SigmaEstimate
    overall: SigmaEstimate


@dataclass(frozen=True, slots=True)
class CapabilityContext:
    """The conditions a capability figure is only valid under (FR-P09).

    Attributes
    ----------
    window
        Start and end of the period the data covers, both timezone-aware. A
        capability figure without a window cannot be compared to the next one.
    stability
        Whether the process was demonstrated to be in control over the window.
    normality
        Result of a normality assessment, if one was performed.
    require_stable
        Refuse to produce indices for a process not demonstrated to be in
        control (FR-P04). Defaults to refusing. Turning it off is a deliberate
        act with a name attached, which is the point.
    """

    window: tuple[datetime, datetime]
    stability: StabilityStatus
    normality: NormalityAssessment | None = None
    require_stable: bool = True


@dataclass(frozen=True, slots=True)
class CapabilityResult:
    """A capability assessment with everything needed to defend it (FR-P09).

    Attributes
    ----------
    parameter_id
        What was assessed.
    within
        Cp and Cpk, from short-term sigma.
    overall
        Pp and Ppk, from long-term sigma. Named separately from ``within``
        because reporting one as the other is the most common way a capability
        claim is overstated.
    cpm
        Taguchi capability, which penalises being off target as well as being
        spread out. ``None`` when the specification names no target.
    n_observations
        Sample size behind the estimate.
    window_start, window_end
        Period the data covers. A capability figure without a window cannot be
        compared to the next one.
    stability
        Whether the process was demonstrated to be in control.
    specification_side
        Which limits existed.
    normality
        The normality assessment, or ``None`` if it was not performed.
    """

    parameter_id: str
    within: CapabilityIndices
    overall: CapabilityIndices
    n_observations: int
    window_start: datetime
    window_end: datetime
    stability: StabilityStatus
    specification_side: SpecificationSide
    cpm: float | None = None
    normality: NormalityAssessment | None = None

    @property
    def sigma_ratio(self) -> float:
        """Long-term sigma over short-term sigma.

        One on a process whose only variation is the noise between consecutive
        units. Two on a process that also wanders between shifts, which is most
        of them. It is the single most informative number on this object and
        the one nobody asks for: a ratio far above one says the gain available
        from controlling drift is larger than the gain available from reducing
        noise.
        """
        return self.overall.sigma / self.within.sigma


def capability(
    values: FloatArray,
    specification: SpecificationLimit,
    *,
    dispersion: DispersionPair,
    context: CapabilityContext,
) -> CapabilityResult:
    """Compute a full capability assessment against a specification.

    Parameters
    ----------
    values
        Observations in the window, in the specification's unit. Order does not
        matter here; the estimators were computed from ordered data upstream.
    specification
        The approved specification, single- or two-sided.
    dispersion
        Short-term and long-term sigma estimates for the same window.
    context
        The window, the stability finding, the normality assessment if any, and
        whether stability is required.

    Returns
    -------
    CapabilityResult
        Within and overall indices, with the conditions attached.

    Raises
    ------
    InsufficientDataError
        If fewer than two observations were supplied.
    UnstableProcessError
        If ``require_stable`` and the process was not shown to be in control.
    DegenerateSeriesError
        If either sigma estimate is not positive.

    References
    ----------
    Montgomery (2019), 8th ed., §8.2-8.3.
    """
    count = int(values.size)
    if count < MIN_CAPABILITY_OBSERVATIONS:
        raise InsufficientDataError(
            "a capability index needs at least two observations",
            n=count,
            required=MIN_CAPABILITY_OBSERVATIONS,
        )
    require_stability(specification, context)
    _require_positive(dispersion.within)
    _require_positive(dispersion.overall)

    mean = float(np.mean(values))
    return CapabilityResult(
        parameter_id=str(specification.parameter_id),
        within=_indices(mean, specification, dispersion.within),
        overall=_indices(mean, specification, dispersion.overall),
        cpm=_cpm(values, specification, dispersion.overall),
        n_observations=count,
        window_start=context.window[0],
        window_end=context.window[1],
        stability=context.stability,
        specification_side=side_of(specification),
        normality=context.normality,
    )


def require_stability(
    specification: SpecificationLimit,
    context: CapabilityContext,
) -> None:
    """Refuse an index for a process that was not shown to repeat itself.

    Parameters
    ----------
    specification
        The specification being assessed, named in the error.
    context
        The stability finding and whether it is being enforced.

    Raises
    ------
    UnstableProcessError
        If stability is required and was not demonstrated (FR-P04).
    """
    if context.require_stable and context.stability is not StabilityStatus.IN_CONTROL:
        raise UnstableProcessError(
            "capability describes a process that is repeating itself, and this "
            "one was not shown to be",
            parameter_id=specification.parameter_id,
            stability=context.stability,
        )


def side_of(specification: SpecificationLimit) -> SpecificationSide:
    """Report which specification limits a specification actually has.

    Parameters
    ----------
    specification
        The approved specification.

    Returns
    -------
    SpecificationSide
        Whether both limits, only the upper, or only the lower exist.
    """
    if specification.lsl is not None and specification.usl is not None:
        return SpecificationSide.BOTH
    if specification.usl is not None:
        return SpecificationSide.UPPER_ONLY
    return SpecificationSide.LOWER_ONLY


def _indices(
    mean: float,
    specification: SpecificationLimit,
    estimate: SigmaEstimate,
) -> CapabilityIndices:
    r"""Compute one family of indices from one dispersion estimate.

    Cp and Pp share this code, as do Cpk and Ppk, because they are the same
    formulae over different sigmas. The estimator travels with the result so
    that a caller holding a bare number can still say which it is.
    """
    sigma = estimate.value
    upper = (
        (specification.usl - mean) / (HALF_SIGMA_SPAN * sigma)
        if specification.usl is not None
        else None
    )
    lower = (
        (mean - specification.lsl) / (HALF_SIGMA_SPAN * sigma)
        if specification.lsl is not None
        else None
    )
    potential = (
        (specification.usl - specification.lsl) / (CAPABILITY_SIGMA_SPAN * sigma)
        if specification.usl is not None and specification.lsl is not None
        else None
    )
    return CapabilityIndices(
        cp=potential,
        cpu=upper,
        cpl=lower,
        cpk=min(value for value in (upper, lower) if value is not None),
        estimator=estimate.estimator,
        sigma=sigma,
    )


def _cpm(
    values: FloatArray,
    specification: SpecificationLimit,
    estimate: SigmaEstimate,
) -> float | None:
    r"""Taguchi capability, which counts distance from target as a loss.

    .. math::
        C_{pm} = \frac{USL - LSL}{6\sqrt{\sigma^2 + (\mu - T)^2}}

    Cpk treats a process centred between the limits and one sitting on target
    as equally good when the target is not the midpoint. Cpm does not, which is
    why it is the index a customer with a nominal-is-best characteristic
    actually wants.

    Returns ``None`` where the specification names no target or is single
    sided, since the numerator is a width.

    References
    ----------
    Chan, Cheng and Spiring (1988), *Journal of Quality Technology* 20(3).
    Montgomery (2019), 8th ed., §8.2.3.
    """
    if specification.target is None:
        return None
    if specification.usl is None or specification.lsl is None:
        return None
    mean = float(np.mean(values))
    offset = mean - specification.target
    tau = float(np.sqrt(estimate.value**2 + offset**2))
    return (specification.usl - specification.lsl) / (CAPABILITY_SIGMA_SPAN * tau)


def _require_positive(estimate: SigmaEstimate) -> None:
    """Refuse a dispersion estimate that would make every index infinite.

    Raises
    ------
    DegenerateSeriesError
        If the estimate is zero or negative.
    """
    if estimate.value <= 0.0:
        raise DegenerateSeriesError(
            "a capability index needs a positive dispersion estimate",
            estimator=estimate.estimator,
            estimate=estimate.value,
        )
