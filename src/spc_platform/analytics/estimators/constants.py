"""Control chart constants, derived from their definitions rather than transcribed.

Every constant here has a closed form or an integral definition in the order
statistics of the normal distribution. This module evaluates those definitions.
It does not hold a table of published values.

That choice is deliberate, and it is the opposite of what most implementations
do. A transcribed table is a list of opportunities to typo a digit, and a typo
in ``d2`` is invisible: limits still render, still look plausible, and are
wrong by a few percent forever. Deriving the constants moves the failure mode
into the open, because a derivation that is wrong is usually wrong everywhere
at once and the reference tests catch it on the first row.

The published tables are still the authority. They appear in
``tests/statistical/analytics/test_constants.py``, where every value this
module computes is checked against Montgomery's Appendix VI. The tables verify
the code; they are not the code.

References
----------
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., Appendix VI, "Factors for Constructing Variables Control Charts".
NIST/SEMATECH e-Handbook of Statistical Methods, §6.3.2, "What are Variables
Control Charts?".
Tippett, L. H. C. (1925). "On the extreme individuals and the range of samples
taken from a normal population." *Biometrika* 17(3/4), 364-387 — the integral
form of the expected range used in :func:`d2`.
"""

from __future__ import annotations

from functools import cache, lru_cache
from math import exp, lgamma, sqrt

import numpy as np
from numpy.polynomial.legendre import leggauss
from numpy.typing import NDArray
from scipy import stats

from spc_platform.common.errors import InsufficientDataError

MIN_SUBGROUP_SIZE = 2
"""Below two observations a subgroup has no range and no standard deviation."""

MAX_TABULATED_SUBGROUP_SIZE = 25
"""The largest subgroup size Montgomery's Appendix VI tabulates.

Nothing here breaks above it — the integrals converge for any n — but a value
beyond the published table cannot be checked against the published table, so
callers are refused rather than quietly trusted. It is also one full carrier of
wafers, which is the largest subgroup this platform has a physical reason to
form.
"""

_INTEGRATION_LIMIT = 12.0
"""Standard deviations either side of the mean to integrate over.

The normal density beyond twelve sigma contributes on the order of 1e-33, far
below the precision any control chart constant is quoted to.
"""

_QUADRATURE_NODES = 160
"""Gauss-Legendre nodes per dimension.

Both integrands are smooth and decay like the normal density, so convergence is
fast: every constant here is stable to seven decimal places from 160 nodes
upward, and agrees with adaptive quadrature to the same precision. Adaptive
integration gives the same answers and takes roughly three hundred times as
long, which matters because the statistical tier has a sixty-second budget.
"""


def _require_valid_subgroup_size(subgroup_size: int) -> None:
    """Reject a subgroup size that no chart constant is defined for.

    Raises
    ------
    InsufficientDataError
        If ``subgroup_size`` is below two or above the largest tabulated size.
    """
    if subgroup_size < MIN_SUBGROUP_SIZE:
        raise InsufficientDataError(
            "a control chart constant needs at least two observations per subgroup",
            subgroup_size=subgroup_size,
            required=MIN_SUBGROUP_SIZE,
        )
    if subgroup_size > MAX_TABULATED_SUBGROUP_SIZE:
        raise InsufficientDataError(
            "subgroup size exceeds the largest published table, so the derived "
            "constant cannot be verified against a reference",
            subgroup_size=subgroup_size,
            required=MAX_TABULATED_SUBGROUP_SIZE,
        )


@cache
def d2(subgroup_size: int) -> float:
    r"""Give the expected range of ``subgroup_size`` standard normal observations.

    The estimator :math:`\bar{R}/d_2` is unbiased for the process standard
    deviation precisely because :math:`d_2` is this expectation.

    Evaluated from Tippett's integral

    .. math::
        d_2(n) = \int_{-\infty}^{\infty}
                 \left[1 - \Phi(x)^n - (1 - \Phi(x))^n\right] dx

    which is the expected range written as the integral of the survival
    function of the maximum minus that of the minimum.

    Parameters
    ----------
    subgroup_size
        Observations per subgroup, at least 2 and at most 25.

    Returns
    -------
    float
        The constant :math:`d_2`, dimensionless.

    Raises
    ------
    InsufficientDataError
        If the subgroup size is outside the supported range.

    References
    ----------
    Montgomery (2019), 8th ed., Appendix VI. Tippett (1925), *Biometrika* 17.
    """
    _require_valid_subgroup_size(subgroup_size)
    x, weights = _line_quadrature()
    above = np.asarray(stats.norm.cdf(x)) ** subgroup_size
    below = np.asarray(stats.norm.sf(x)) ** subgroup_size
    return float(np.sum(weights * (1.0 - above - below)))


@cache
def d3(subgroup_size: int) -> float:
    r"""Give the standard deviation of the range of ``subgroup_size`` standard normals.

    Sets the width of the R chart: the range has standard deviation
    :math:`d_3 \sigma`, so its three-sigma limits sit at
    :math:`\bar{R} \pm 3 d_3 \bar{R} / d_2`, which is what :func:`D3` and
    :func:`D4` package.

    Obtained as :math:`\sqrt{E[W^2] - d_2^2}`, with the second moment from the
    joint density of the sample minimum and maximum

    .. math::
        E[W^2] = n(n-1) \int_{-\infty}^{\infty} \int_{x}^{\infty}
                 (y-x)^2 \phi(x) \phi(y)
                 \left[\Phi(y) - \Phi(x)\right]^{n-2} dy\, dx

    Parameters
    ----------
    subgroup_size
        Observations per subgroup, at least 2 and at most 25.

    Returns
    -------
    float
        The constant :math:`d_3`, dimensionless.

    Raises
    ------
    InsufficientDataError
        If the subgroup size is outside the supported range.

    References
    ----------
    Montgomery (2019), 8th ed., Appendix VI.
    David, H. A. and Nagaraja, H. N. (2003). *Order Statistics*, 3rd ed.,
    §3.2 — the joint density of the extremes used above.
    """
    _require_valid_subgroup_size(subgroup_size)
    lower, lower_weights = _line_quadrature()
    fraction, fraction_weights = _unit_quadrature()

    # The upper variable runs from the lower one to the truncation point, which
    # is not a rectangle. Rescaling it onto the unit interval makes it one, at
    # the cost of the ``span`` Jacobian below.
    minimum = lower[:, np.newaxis]
    span = _INTEGRATION_LIMIT - minimum
    maximum = minimum + fraction[np.newaxis, :] * span

    covered = np.asarray(stats.norm.cdf(maximum) - stats.norm.cdf(minimum))
    between = covered ** (subgroup_size - 2) if subgroup_size > MIN_SUBGROUP_SIZE else 1.0
    density = np.asarray(stats.norm.pdf(minimum) * stats.norm.pdf(maximum))
    integrand = (maximum - minimum) ** 2 * density * between * span

    weights = lower_weights[:, np.newaxis] * fraction_weights[np.newaxis, :]
    pairs = subgroup_size * (subgroup_size - 1)
    second_moment = pairs * float(np.sum(weights * integrand))
    return sqrt(second_moment - d2(subgroup_size) ** 2)


@lru_cache(maxsize=1)
def _line_quadrature() -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Nodes and weights over the truncated real line."""
    nodes, weights = leggauss(_QUADRATURE_NODES)
    return nodes * _INTEGRATION_LIMIT, weights * _INTEGRATION_LIMIT


@lru_cache(maxsize=1)
def _unit_quadrature() -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Nodes and weights over the unit interval."""
    nodes, weights = leggauss(_QUADRATURE_NODES)
    return 0.5 * (nodes + 1.0), 0.5 * weights


@cache
def c4(subgroup_size: int) -> float:
    r"""Ratio of the expected sample standard deviation to the true one.

    The sample standard deviation understates :math:`\sigma` — Jensen's
    inequality applied to the square root — so :math:`\bar{s}/c_4` is the
    unbiased estimator, not :math:`\bar{s}`. At n = 5 the correction is 6%,
    which is large enough to move a limit and small enough to be dismissed as
    noise by anyone not looking for it.

    .. math::
        c_4(n) = \sqrt{\frac{2}{n-1}}
                 \frac{\Gamma(n/2)}{\Gamma((n-1)/2)}

    Computed through log-gamma, because the gamma function itself overflows
    around n = 340 while the ratio stays close to one.

    Parameters
    ----------
    subgroup_size
        Observations per subgroup, at least 2 and at most 25.

    Returns
    -------
    float
        The constant :math:`c_4`, dimensionless and below 1.

    Raises
    ------
    InsufficientDataError
        If the subgroup size is outside the supported range.

    References
    ----------
    Montgomery (2019), 8th ed., §6.3.1 and Appendix VI.
    NIST/SEMATECH e-Handbook, §6.3.2.
    """
    _require_valid_subgroup_size(subgroup_size)
    half = subgroup_size / 2.0
    log_ratio = lgamma(half) - lgamma(half - 0.5)
    return float(sqrt(2.0 / (subgroup_size - 1)) * exp(log_ratio))


def a2(subgroup_size: int) -> float:
    r"""X-bar chart limit factor when sigma is estimated from the mean range.

    :math:`A_2 = 3 / (d_2 \sqrt{n})`, so that
    :math:`\bar{\bar{x}} \pm A_2 \bar{R}` is three standard errors of the
    subgroup mean.

    Parameters
    ----------
    subgroup_size
        Observations per subgroup, at least 2 and at most 25.

    Returns
    -------
    float
        The constant :math:`A_2`, dimensionless.

    References
    ----------
    Montgomery (2019), 8th ed., §6.2.1 and Appendix VI.
    """
    return 3.0 / (d2(subgroup_size) * sqrt(subgroup_size))


def a3(subgroup_size: int) -> float:
    r"""X-bar chart limit factor when sigma is estimated from the mean sigma.

    :math:`A_3 = 3 / (c_4 \sqrt{n})`.

    Parameters
    ----------
    subgroup_size
        Observations per subgroup, at least 2 and at most 25.

    Returns
    -------
    float
        The constant :math:`A_3`, dimensionless.

    References
    ----------
    Montgomery (2019), 8th ed., §6.3.1 and Appendix VI.
    """
    return 3.0 / (c4(subgroup_size) * sqrt(subgroup_size))


def d3_lower(subgroup_size: int) -> float:
    r"""Lower R chart limit factor, :math:`D_3 = \max(0, 1 - 3 d_3 / d_2)`.

    Truncated at zero because a range cannot be negative. Below n = 7 the
    untruncated value is negative and the R chart therefore has no lower limit
    — a fact the truncation encodes rather than hides.

    Parameters
    ----------
    subgroup_size
        Observations per subgroup, at least 2 and at most 25.

    Returns
    -------
    float
        The constant :math:`D_3`, dimensionless, zero below n = 7.

    References
    ----------
    Montgomery (2019), 8th ed., §6.2.1 and Appendix VI.
    """
    return max(0.0, 1.0 - 3.0 * d3(subgroup_size) / d2(subgroup_size))


def d4_upper(subgroup_size: int) -> float:
    r"""Upper R chart limit factor, :math:`D_4 = 1 + 3 d_3 / d_2`.

    Parameters
    ----------
    subgroup_size
        Observations per subgroup, at least 2 and at most 25.

    Returns
    -------
    float
        The constant :math:`D_4`, dimensionless.

    References
    ----------
    Montgomery (2019), 8th ed., §6.2.1 and Appendix VI.
    """
    return 1.0 + 3.0 * d3(subgroup_size) / d2(subgroup_size)


def b3(subgroup_size: int) -> float:
    r"""Lower s chart limit factor, :math:`B_3 = \max(0, 1 - 3\sqrt{1-c_4^2}/c_4)`.

    Truncated at zero for the same reason as :func:`d3_lower`: a standard
    deviation cannot be negative, and below n = 6 the untruncated value is.

    Parameters
    ----------
    subgroup_size
        Observations per subgroup, at least 2 and at most 25.

    Returns
    -------
    float
        The constant :math:`B_3`, dimensionless, zero below n = 6.

    References
    ----------
    Montgomery (2019), 8th ed., §6.3.1 and Appendix VI.
    """
    return max(0.0, 1.0 - 3.0 * _relative_sigma_of_s(subgroup_size))


def b4(subgroup_size: int) -> float:
    r"""Upper s chart limit factor, :math:`B_4 = 1 + 3\sqrt{1-c_4^2}/c_4`.

    Parameters
    ----------
    subgroup_size
        Observations per subgroup, at least 2 and at most 25.

    Returns
    -------
    float
        The constant :math:`B_4`, dimensionless.

    References
    ----------
    Montgomery (2019), 8th ed., §6.3.1 and Appendix VI.
    """
    return 1.0 + 3.0 * _relative_sigma_of_s(subgroup_size)


def e2(subgroup_size: int) -> float:
    r"""Individuals chart limit factor, :math:`E_2 = 3 / d_2`.

    Applied to the mean moving range. For the usual moving range of span two,
    ``subgroup_size`` is 2 and :math:`E_2 = 2.660`.

    Parameters
    ----------
    subgroup_size
        Span of the moving range, at least 2 and at most 25.

    Returns
    -------
    float
        The constant :math:`E_2`, dimensionless.

    References
    ----------
    Montgomery (2019), 8th ed., §6.4 and Appendix VI.
    """
    return 3.0 / d2(subgroup_size)


def _relative_sigma_of_s(subgroup_size: int) -> float:
    r""":math:`\sqrt{1-c_4^2}/c_4` — the standard deviation of s over its mean.

    Both the s chart limit factors are one plus or minus three of this, so it
    is named once rather than written twice.
    """
    corrected = c4(subgroup_size)
    return sqrt(1.0 - corrected**2) / corrected


def normal_quantile(probability: float) -> float:
    """Invert the standard normal, translating a false-alarm rate into sigma.

    Parameters
    ----------
    probability
        Cumulative probability, strictly between 0 and 1.

    Returns
    -------
    float
        The value ``z`` with ``P(Z <= z) == probability``.

    References
    ----------
    NIST/SEMATECH e-Handbook, §1.3.6.6.1.
    """
    return float(stats.norm.ppf(probability))


def two_sided_exceedance(sigma_multiplier: float) -> float:
    """Probability a normal deviate falls outside +/- ``sigma_multiplier``.

    At the conventional three sigma this is 0.0027, whose reciprocal is the
    familiar in-control average run length of 370.

    Parameters
    ----------
    sigma_multiplier
        Limit width in standard deviations, positive.

    Returns
    -------
    float
        The two-sided tail probability.

    References
    ----------
    Montgomery (2019), 8th ed., §5.3.2.
    """
    return float(2.0 * stats.norm.sf(sigma_multiplier))
