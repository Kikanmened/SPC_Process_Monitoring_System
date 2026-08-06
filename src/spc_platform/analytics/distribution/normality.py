"""Assessing normality, and doing something useful when it fails.

Every capability index in the usual form assumes a normal process, and several
of the parameters a fab cares about are not normal by construction. Particle
counts are bounded below by zero and skewed right. Overlay error is a
magnitude, so it is folded. Etch rate is usually fine. Applying the normal
formulae regardless does not produce an error; it produces a Cpk that is wrong
in a direction that depends on the skew, and that nobody can detect by looking
at it.

So the assessment is recorded with the result (FR-P06), and where it fails
there are two supported routes (FR-P07): transform the data to normality and
compute the indices there, or abandon the normal formula and use the
distribution's own percentiles. Both record which was used, because a Cpk from
a Box-Cox transform and one from a percentile fit are not comparable and will
be compared anyway.

References
----------
NIST/SEMATECH e-Handbook of Statistical Methods, §1.3.5.14 (Anderson-Darling),
§6.5.2 (non-normal capability).
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §8.3.3.
Clements, J. A. (1989). "Process Capability Calculations for Non-Normal
Distributions." *Quality Progress* 22(9), 95-100.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from scipy import special, stats

from spc_platform.common.errors import (
    ConfigurationError,
    DegenerateSeriesError,
    InsufficientDataError,
)
from spc_platform.common.types import FloatArray

DEFAULT_SIGNIFICANCE = 0.05
"""Significance level for the normality test.

Five percent, which means a normal process is declared non-normal about one
time in twenty. That is the conventional choice and it has a consequence worth
stating: on a fab with two thousand charted parameters, a hundred of them will
fail this test every time it is run on data that is perfectly normal.
"""

MIN_NORMALITY_OBSERVATIONS = 8
"""Below eight observations the Anderson-Darling critical values are not tabulated.

A test with no power is worse than no test, because its passing result gets
recorded as evidence.
"""

NATURAL_TOLERANCE_QUANTILES = (0.00135, 0.99865)
"""The percentiles a normal process puts at plus and minus three sigma.

The percentile method replaces "six sigma" with the distance between these two
quantiles of whatever distribution actually fits, which reduces to the normal
answer when the distribution is normal.
"""

MIN_TRANSFORM_OBSERVATIONS = 20
"""Fitting a transformation parameter from fewer points fits the noise."""


class CapabilityMethod(StrEnum):
    """How a capability index handled the shape of the distribution (FR-P07)."""

    NORMAL = "normal"
    BOX_COX = "box_cox"
    PERCENTILE = "percentile"


@dataclass(frozen=True, slots=True)
class NormalityAssessment:
    """Whether an index rests on an assumption that holds (FR-P06).

    Attributes
    ----------
    statistic
        Anderson-Darling test statistic.
    critical_value
        Tabulated critical value at ``significance``.
    significance
        Level the critical value is for.
    is_normal
        Whether the hypothesis of normality survives at that level. Recorded
        rather than acted on: this package states what the data looks like, and
        the application decides what to do about it.
    method
        How the data was handled before the test — fitted as it stands, or
        transformed first.
    """

    statistic: float
    critical_value: float
    significance: float
    is_normal: bool
    method: str


@dataclass(frozen=True, slots=True)
class NaturalTolerance:
    """The spread of a process, stated without assuming it is normal.

    Attributes
    ----------
    lower, upper
        The 0.135th and 99.865th percentiles, which for a normal process are
        the three sigma points.
    median
        The 50th percentile, which replaces the mean as the centre when the
        distribution is skewed and the mean is not where most of the material
        is.
    method
        How these were obtained.
    distribution
        Name of the fitted distribution, or ``None`` for the empirical case.
    """

    lower: float
    upper: float
    median: float
    method: CapabilityMethod
    distribution: str | None = None

    @property
    def width(self) -> float:
        """Distance between the tolerance percentiles, replacing six sigma."""
        return self.upper - self.lower


def assess_normality(
    values: FloatArray,
    *,
    significance: float = DEFAULT_SIGNIFICANCE,
    method: CapabilityMethod = CapabilityMethod.NORMAL,
) -> NormalityAssessment:
    """Test the hypothesis that the observations came from a normal distribution.

    Uses Anderson-Darling, which weights the tails more heavily than
    Kolmogorov-Smirnov. That matters here more than in most applications: a
    capability index is almost entirely a statement about the tails, so a test
    that fits the middle well and the tails poorly would pass exactly the
    distributions that break the index.

    Parameters
    ----------
    values
        Observations, in any order.
    significance
        Level to compare against, from the tabulated set 0.15, 0.10, 0.05,
        0.025, and 0.01.
    method
        Recorded on the result, so an assessment made after a transformation
        says so.

    Returns
    -------
    NormalityAssessment
        The statistic, the critical value, and whether normality survived.

    Raises
    ------
    InsufficientDataError
        If there are too few observations for the tabulated critical values.
    DegenerateSeriesError
        If every observation is identical.

    References
    ----------
    NIST/SEMATECH e-Handbook, §1.3.5.14.
    """
    count = int(values.size)
    if count < MIN_NORMALITY_OBSERVATIONS:
        raise InsufficientDataError(
            "too few observations for a normality test with any power",
            n=count,
            required=MIN_NORMALITY_OBSERVATIONS,
        )
    if float(np.ptp(values)) <= 0.0:
        raise DegenerateSeriesError(
            "every observation is identical, so no distribution can be fitted",
            n=count,
        )
    outcome = stats.anderson(values, dist="norm")
    critical = _critical_value(
        np.asarray(outcome.significance_level, dtype=np.float64),
        np.asarray(outcome.critical_values, dtype=np.float64),
        significance,
    )
    return NormalityAssessment(
        statistic=float(outcome.statistic),
        critical_value=critical,
        significance=significance,
        is_normal=bool(outcome.statistic < critical),
        method=str(method),
    )


def natural_tolerance(
    values: FloatArray,
    *,
    method: CapabilityMethod = CapabilityMethod.PERCENTILE,
) -> NaturalTolerance:
    """Find the spread of a process without assuming a shape for it.

    Parameters
    ----------
    values
        Observations, in any order.
    method
        ``PERCENTILE`` reads the quantiles off the empirical distribution.
        ``BOX_COX`` transforms to approximate normality first, takes the normal
        three sigma points there, and transforms them back — which extrapolates
        into tails the sample never reached, and is therefore the better choice
        on a small sample and the worse one on a large sample whose tail is
        real.

    Returns
    -------
    NaturalTolerance
        Percentiles standing in for the three sigma points.

    Raises
    ------
    InsufficientDataError
        If there are too few observations for the requested method.
    DegenerateSeriesError
        If every observation is identical.
    ConfigurationError
        If ``method`` is ``NORMAL``, which is not a non-normal method.

    References
    ----------
    NIST/SEMATECH e-Handbook, §6.5.2. Clements (1989), *Quality Progress* 22(9).
    """
    if float(np.ptp(values)) <= 0.0:
        raise DegenerateSeriesError(
            "every observation is identical, so the process has no spread",
            n=int(values.size),
        )
    lower_quantile, upper_quantile = NATURAL_TOLERANCE_QUANTILES

    if method is CapabilityMethod.PERCENTILE:
        lower, median, upper = np.quantile(values, [lower_quantile, 0.5, upper_quantile])
        return NaturalTolerance(
            lower=float(lower),
            upper=float(upper),
            median=float(median),
            method=method,
            distribution="empirical",
        )

    if method is CapabilityMethod.BOX_COX:
        return _box_cox_tolerance(values, lower_quantile, upper_quantile)

    raise ConfigurationError(
        "a natural tolerance needs a non-normal method; the normal case is the "
        "ordinary six-sigma width",
        method=method,
    )


def _box_cox_tolerance(
    values: FloatArray,
    lower_quantile: float,
    upper_quantile: float,
) -> NaturalTolerance:
    """Transform to normality, take the tolerance there, and transform back.

    Raises
    ------
    InsufficientDataError
        If there are too few observations to fit the transformation parameter,
        or if any value is not strictly positive — Box-Cox is undefined at and
        below zero, and shifting the data to make it fit changes the answer
        without saying so.
    """
    count = int(values.size)
    if count < MIN_TRANSFORM_OBSERVATIONS:
        raise InsufficientDataError(
            "too few observations to fit a Box-Cox transformation",
            n=count,
            required=MIN_TRANSFORM_OBSERVATIONS,
        )
    if float(np.min(values)) <= 0.0:
        raise InsufficientDataError(
            "Box-Cox needs strictly positive values; shifting them to fit would "
            "change the answer silently",
            minimum=float(np.min(values)),
        )
    transformed, fitted = stats.boxcox(values)
    power = float(fitted)
    mean = float(np.mean(transformed))
    spread = float(np.std(transformed, ddof=1))
    bounds = [
        mean + stats.norm.ppf(quantile) * spread
        for quantile in (lower_quantile, 0.5, upper_quantile)
    ]
    lower, median, upper = (float(special.inv_boxcox(bound, power)) for bound in bounds)
    return NaturalTolerance(
        lower=lower,
        upper=upper,
        median=median,
        method=CapabilityMethod.BOX_COX,
        distribution=f"box-cox(lambda={power:.4f})",
    )


def _critical_value(
    percentages: FloatArray,
    criticals: FloatArray,
    significance: float,
) -> float:
    """Pick the tabulated critical value for the requested significance.

    Raises
    ------
    ConfigurationError
        If the level is not one that is tabulated. Interpolating between
        published values would produce a threshold nobody published, and the
        resulting pass or fail would be uncheckable.
    """
    matches = np.flatnonzero(np.isclose(percentages, significance * 100.0))
    if matches.size == 0:
        raise ConfigurationError(
            "significance level is not tabulated for this test",
            significance=significance,
            available=sorted(float(value) / 100.0 for value in percentages),
        )
    return float(criticals[matches[0]])
