r"""Bias, linearity, and stability of a measurement system (FR-M04).

Gauge R&R measures how much a gauge *scatters*. These three measure whether it
is pointing at the right place, and they are independent of it: a gauge can be
beautifully repeatable and consistently read 3 nm high, and no amount of
repeated measurement will reveal that. Only a reference standard will.

The three answer different questions and fail differently.

**Bias** is a constant offset at one reference value. It is the easiest to fix,
by calibration, and the easiest to miss, because every chart and every capability
index is invariant to it right up until a customer measures the same part on a
different tool.

**Linearity** is bias that changes across the operating range. A gauge reading
correctly at the middle of its range and 5% high at the top will pass a bias
study run at nominal and fail every part at the specification limit — which is
exactly the population a specification is about.

**Stability** is bias that changes over time, and it is the one that needs a
control chart rather than a hypothesis test, because the question is not whether
today's mean differs from the reference but whether the drift is a trend.

References
----------
NIST/SEMATECH e-Handbook of Statistical Methods, §2.3.3 (bias and linearity of
a measurement process), §2.4.
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §8.7.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from spc_platform.common.errors import (
    ConfigurationError,
    DegenerateSeriesError,
    InsufficientDataError,
)
from spc_platform.common.types import FloatArray

DEFAULT_SIGNIFICANCE = 0.05
"""Level at which a bias or a slope is called real."""

MIN_BIAS_MEASUREMENTS = 2
"""Two measurements give a standard error, which is the least a test needs."""

MIN_LINEARITY_LEVELS = 3
"""Below three reference values a line cannot be distinguished from two points.

Two points define a line exactly, so the fit has no residual and the slope
cannot be tested. Five levels spanning the operating range is the usual
recommendation.
"""


@dataclass(frozen=True, slots=True)
class BiasResult:
    """How far off, and whether that is more than noise.

    Attributes
    ----------
    bias
        Mean measurement minus the reference value, in measurement units.
        Signed: positive means the gauge reads high.
    reference_value
        The accepted value of the standard measured.
    mean_measurement
        What the gauge said, on average.
    standard_error
        Standard error of the mean measurement.
    t_statistic, p_value, degrees_of_freedom
        Test of the hypothesis that the true bias is zero.
    confidence_interval
        Interval for the bias at ``1 - significance``. More useful than the
        p-value: a study large enough will find a statistically significant
        bias of 0.001 nm, and the interval is what says whether it matters.
    significance
        Level the interval and the verdict are for.
    is_significant
        Whether zero bias was rejected.
    n_measurements
        Repeat measurements of the standard.
    """

    bias: float
    reference_value: float
    mean_measurement: float
    standard_error: float
    t_statistic: float
    p_value: float
    degrees_of_freedom: int
    confidence_interval: tuple[float, float]
    significance: float
    is_significant: bool
    n_measurements: int


@dataclass(frozen=True, slots=True)
class LinearityResult:
    """Whether the bias stays put across the operating range.

    Attributes
    ----------
    slope, intercept
        Least squares fit of bias against reference value. A slope of zero
        means constant bias, which is a calibration problem; a non-zero slope
        means the gauge's error depends on what it is measuring, which is not
        fixable by calibration.
    slope_standard_error, slope_p_value
        Test of the hypothesis that the slope is zero.
    r_squared
        Share of the bias variation the line explains.
    significance
        Level the verdict is for.
    is_linear
        True when no slope was detected — that is, when the bias is constant
        and the gauge is *linear* in the metrology sense. The name is the
        source's, and it means the opposite of what it sounds like: a gauge
        with a strong straight-line relationship between bias and magnitude
        has a linearity *problem*.
    n_levels, n_measurements
        Reference values used, and total measurements across them.
    """

    slope: float
    intercept: float
    slope_standard_error: float
    slope_p_value: float
    r_squared: float
    significance: float
    is_linear: bool
    n_levels: int
    n_measurements: int

    def linearity(self, process_variation: float) -> float:
        """Express the slope as a width, comparable with the other MSA figures.

        Parameters
        ----------
        process_variation
            The six sigma span of the process the gauge is used on.

        Returns
        -------
        float
            ``|slope| * process_variation``: how much the bias moves across the
            range the gauge actually works over. A steep slope over a narrow
            range may matter less than a shallow one over a wide range, and the
            bare slope cannot say which case it is.
        """
        return abs(self.slope) * process_variation


def bias(
    measurements: FloatArray,
    reference_value: float,
    *,
    significance: float = DEFAULT_SIGNIFICANCE,
) -> BiasResult:
    r"""Test whether a gauge reads a known standard correctly.

    .. math::
        t = \frac{\bar{x} - x_{\text{ref}}}{s / \sqrt{n}}

    A one-sample t-test against the accepted value. The interval matters more
    than the verdict: with enough measurements any real gauge shows a
    statistically significant bias, and the question an engineer needs answered
    is how large it might be, not whether it is exactly zero.

    Parameters
    ----------
    measurements
        Repeat measurements of the standard, in its unit.
    reference_value
        The accepted value of the standard, from a calibration certificate.
    significance
        Level for the interval and the verdict.

    Returns
    -------
    BiasResult
        The offset, its interval, and whether zero was rejected.

    Raises
    ------
    InsufficientDataError
        If there are fewer than two measurements.
    DegenerateSeriesError
        If every measurement is identical, so the standard error is zero and
        the statistic is undefined.
    ConfigurationError
        If the significance level is not in ``(0, 1)``.

    References
    ----------
    NIST/SEMATECH e-Handbook, §2.3.3.
    """
    _require_significance(significance)
    count = int(measurements.size)
    if count < MIN_BIAS_MEASUREMENTS:
        raise InsufficientDataError(
            "a bias study needs at least two measurements of the standard",
            n=count,
            required=MIN_BIAS_MEASUREMENTS,
        )
    spread = float(np.std(measurements, ddof=1))
    if spread <= 0.0:
        raise DegenerateSeriesError(
            "every measurement of the standard is identical, so the bias has no "
            "standard error and cannot be tested",
            n=count,
        )

    mean = float(np.mean(measurements))
    offset = mean - reference_value
    standard_error = spread / np.sqrt(count)
    degrees_of_freedom = count - 1
    statistic = offset / standard_error
    p_value = float(2.0 * stats.t.sf(abs(statistic), degrees_of_freedom))
    half_width = float(stats.t.ppf(1.0 - significance / 2.0, degrees_of_freedom) * standard_error)
    return BiasResult(
        bias=offset,
        reference_value=reference_value,
        mean_measurement=mean,
        standard_error=standard_error,
        t_statistic=statistic,
        p_value=p_value,
        degrees_of_freedom=degrees_of_freedom,
        confidence_interval=(offset - half_width, offset + half_width),
        significance=significance,
        is_significant=p_value < significance,
        n_measurements=count,
    )


def linearity(
    reference_values: FloatArray,
    measurements: FloatArray,
    *,
    significance: float = DEFAULT_SIGNIFICANCE,
) -> LinearityResult:
    r"""Test whether the bias changes across the gauge's operating range.

    Regresses the bias of each measurement on the reference value it came from:

    .. math::
        (y_i - x_i) = \beta_0 + \beta_1 x_i + \varepsilon_i

    Regressing the *bias* rather than the measurement is what makes the null
    hypothesis "the slope is zero". Regressing the measurement on the reference
    would put the null at a slope of one, which is the same test written so that
    the interesting answer is the one that looks unremarkable.

    Parameters
    ----------
    reference_values
        Accepted value for each measurement. At least three distinct values,
        spanning the range the gauge is used over.
    measurements
        What the gauge read, aligned with ``reference_values``.
    significance
        Level for the slope test.

    Returns
    -------
    LinearityResult
        Slope, intercept, fit quality, and whether a slope was detected.

    Raises
    ------
    InsufficientDataError
        If the arrays disagree in length, or there are too few distinct
        reference values to fit and test a line.
    DegenerateSeriesError
        If every bias is identical, leaving no residual variation.
    ConfigurationError
        If the significance level is not in ``(0, 1)``.

    References
    ----------
    NIST/SEMATECH e-Handbook, §2.3.3. Montgomery (2019), 8th ed., §8.7.
    """
    _require_significance(significance)
    if reference_values.size != measurements.size:
        raise InsufficientDataError(
            "every measurement needs the reference value it was taken against",
            references=int(reference_values.size),
            measurements=int(measurements.size),
        )
    levels = int(np.unique(reference_values).size)
    if levels < MIN_LINEARITY_LEVELS:
        raise InsufficientDataError(
            "two reference values define a line exactly, leaving no residual to "
            "test the slope against",
            n_levels=levels,
            required=MIN_LINEARITY_LEVELS,
        )

    offsets = measurements - reference_values
    if float(np.ptp(offsets)) <= 0.0:
        raise DegenerateSeriesError(
            "the bias is identical at every reference value, so the fit has no "
            "residual variance and the slope cannot be tested",
            n=int(offsets.size),
        )

    fit = stats.linregress(reference_values, offsets)
    return LinearityResult(
        slope=float(fit.slope),
        intercept=float(fit.intercept),
        slope_standard_error=float(fit.stderr),
        slope_p_value=float(fit.pvalue),
        r_squared=float(fit.rvalue**2),
        significance=significance,
        is_linear=bool(fit.pvalue >= significance),
        n_levels=levels,
        n_measurements=int(measurements.size),
    )


def _require_significance(significance: float) -> None:
    """Refuse a significance level that is not a probability.

    Raises
    ------
    ConfigurationError
        If the level is not strictly inside ``(0, 1)``.
    """
    if not 0.0 < significance < 1.0:
        raise ConfigurationError(
            "a significance level is a probability strictly between zero and one",
            significance=significance,
        )
