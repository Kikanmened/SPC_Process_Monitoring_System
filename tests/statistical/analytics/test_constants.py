"""Chart constants against Montgomery's published table and their closed forms.

Three independent authorities, because this module is derived rather than
transcribed and a derivation can be wrong in ways a table cannot.

1. The published table (Montgomery, Appendix VI) for n = 2 to 10, to the three
   decimal places it is printed to.
2. Exact closed forms at n = 2, where the range of two normals reduces to a
   half-normal and every constant has an elementary expression.
3. Seeded Monte Carlo over the definitions themselves, which covers the
   subgroup sizes above the transcribed rows without transcribing more of them.

The third is what makes the first two more than a spot check. If the quadrature
were subtly wrong at large n, the table rows at small n would still pass.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Callable

import numpy as np
import pytest

from spc_platform.analytics.estimators import constants
from spc_platform.common.errors import InsufficientDataError

pytestmark = pytest.mark.statistical

# Montgomery (2019), 8th ed., Appendix VI, "Factors for Constructing Variables
# Control Charts", rows n = 2 to 10. Printed to three decimal places, which is
# the tolerance the assertions use.
APPENDIX_VI: dict[int, dict[str, float]] = {
    2: {
        "d2": 1.128,
        "d3": 0.853,
        "c4": 0.7979,
        "A2": 1.880,
        "A3": 2.659,
        "B3": 0.000,
        "B4": 3.267,
        "D3": 0.000,
        "D4": 3.267,
    },
    3: {
        "d2": 1.693,
        "d3": 0.888,
        "c4": 0.8862,
        "A2": 1.023,
        "A3": 1.954,
        "B3": 0.000,
        "B4": 2.568,
        "D3": 0.000,
        "D4": 2.574,
    },
    4: {
        "d2": 2.059,
        "d3": 0.880,
        "c4": 0.9213,
        "A2": 0.729,
        "A3": 1.628,
        "B3": 0.000,
        "B4": 2.266,
        "D3": 0.000,
        "D4": 2.282,
    },
    5: {
        "d2": 2.326,
        "d3": 0.864,
        "c4": 0.9400,
        "A2": 0.577,
        "A3": 1.427,
        "B3": 0.000,
        "B4": 2.089,
        "D3": 0.000,
        "D4": 2.114,
    },
    6: {
        "d2": 2.534,
        "d3": 0.848,
        "c4": 0.9515,
        "A2": 0.483,
        "A3": 1.287,
        "B3": 0.030,
        "B4": 1.970,
        "D3": 0.000,
        "D4": 2.004,
    },
    7: {
        "d2": 2.704,
        "d3": 0.833,
        "c4": 0.9594,
        "A2": 0.419,
        "A3": 1.182,
        "B3": 0.118,
        "B4": 1.882,
        "D3": 0.076,
        "D4": 1.924,
    },
    8: {
        "d2": 2.847,
        "d3": 0.820,
        "c4": 0.9650,
        "A2": 0.373,
        "A3": 1.099,
        "B3": 0.185,
        "B4": 1.815,
        "D3": 0.136,
        "D4": 1.864,
    },
    9: {
        "d2": 2.970,
        "d3": 0.808,
        "c4": 0.9693,
        "A2": 0.337,
        "A3": 1.032,
        "B3": 0.239,
        "B4": 1.761,
        "D3": 0.184,
        "D4": 1.816,
    },
    10: {
        "d2": 3.078,
        "d3": 0.797,
        "c4": 0.9727,
        "A2": 0.308,
        "A3": 0.975,
        "B3": 0.284,
        "B4": 1.716,
        "D3": 0.223,
        "D4": 1.777,
    },
}

PUBLISHED_PRECISION = 0.0005
"""Half a unit in the last printed place of the three-decimal columns."""

C4_PRECISION = 0.00005
"""Appendix VI prints c4 to four places, so it is held to a tighter bound."""

TABULATED_SIZES = sorted(APPENDIX_VI)

PRIMARY = ("d2", "d3", "c4")
"""The three constants defined directly by the normal order statistics.

Everything else in the table is arithmetic on these, so only these three are
compared against the table at its full printed precision.
"""

# Each derived constant as its defining formula, so the test states the
# relationship it is checking instead of trusting the implementation's version
# of it. Arguments are the published primary constants and the subgroup size.
DERIVED: dict[str, Callable[[float, float, float, int], float]] = {
    "A2": lambda d2, _d3, _c4, n: 3.0 / (d2 * math.sqrt(n)),
    "A3": lambda _d2, _d3, c4, n: 3.0 / (c4 * math.sqrt(n)),
    "B3": lambda _d2, _d3, c4, _n: max(0.0, 1.0 - 3.0 * math.sqrt(1.0 - c4**2) / c4),
    "B4": lambda _d2, _d3, c4, _n: 1.0 + 3.0 * math.sqrt(1.0 - c4**2) / c4,
    "D3": lambda d2, d3, _c4, _n: max(0.0, 1.0 - 3.0 * d3 / d2),
    "D4": lambda d2, d3, _c4, _n: 1.0 + 3.0 * d3 / d2,
}


def _computed(subgroup_size: int) -> dict[str, float]:
    """Every tabulated constant, as this codebase derives it."""
    return {
        "d2": constants.d2(subgroup_size),
        "d3": constants.d3(subgroup_size),
        "c4": constants.c4(subgroup_size),
        "A2": constants.a2(subgroup_size),
        "A3": constants.a3(subgroup_size),
        "B3": constants.b3(subgroup_size),
        "B4": constants.b4(subgroup_size),
        "D3": constants.d3_lower(subgroup_size),
        "D4": constants.d4_upper(subgroup_size),
    }


def _band(
    formula: Callable[[float, float, float, int], float],
    subgroup_size: int,
) -> tuple[float, float]:
    """Values a derived constant can take across the table's own rounding.

    Appendix VI prints d2 and d3 to three decimals and c4 to four, and its
    derived columns are arithmetic on those printed figures. So the published
    D4 is not a single number but any value consistent with d2 and d3 known to
    half a unit in their last place. Evaluating the formula at the corners of
    that box gives the interval, since each formula is monotone in each of its
    arguments.
    """
    published = APPENDIX_VI[subgroup_size]
    boxes = (
        (published["d2"] - PUBLISHED_PRECISION, published["d2"] + PUBLISHED_PRECISION),
        (published["d3"] - PUBLISHED_PRECISION, published["d3"] + PUBLISHED_PRECISION),
        (published["c4"] - C4_PRECISION, published["c4"] + C4_PRECISION),
    )
    corners = [formula(d2, d3, c4, subgroup_size) for d2, d3, c4 in itertools.product(*boxes)]
    return min(corners), max(corners)


class TestThePrimaryConstants:
    """d2, d3, and c4 against Appendix VI at its full printed precision."""

    @pytest.mark.parametrize("subgroup_size", TABULATED_SIZES)
    @pytest.mark.parametrize("name", PRIMARY)
    def test_the_value_matches_appendix_vi(self, name: str, subgroup_size: int) -> None:
        """Montgomery (2019), 8th ed., Appendix VI.

        These three are what the quadrature and the gamma ratio compute
        directly, so they are held to half a unit in the last printed place
        with nothing propagated in.
        """
        tolerance = C4_PRECISION if name == "c4" else PUBLISHED_PRECISION
        assert _computed(subgroup_size)[name] == pytest.approx(
            APPENDIX_VI[subgroup_size][name], abs=tolerance
        )


class TestTheDerivedConstants:
    """A2, A3, B3, B4, D3, and D4 against the table, allowing for its rounding.

    These columns are arithmetic on figures the table itself prints rounded, so
    an exact derivation does not have to reproduce them digit for digit and
    should not be forced to. At n = 3 the published D4 of 2.574 is what the
    rounded d2 and d3 give, while the exact value is 2.5746; at n = 2 the
    published 3.267 is the exact value and the rounded inputs would give 3.269.
    The table is not consistent about which it prints, so the test asserts what
    is actually true of both: the exact value lies inside the interval the
    published precision allows.
    """

    @pytest.mark.parametrize("subgroup_size", TABULATED_SIZES)
    @pytest.mark.parametrize("name", sorted(DERIVED))
    def test_the_value_is_consistent_with_appendix_vi(self, name: str, subgroup_size: int) -> None:
        """Montgomery (2019), 8th ed., Appendix VI, with rounding propagated."""
        lower, upper = _band(DERIVED[name], subgroup_size)
        computed = _computed(subgroup_size)[name]
        assert lower <= computed <= upper

    @pytest.mark.parametrize("subgroup_size", TABULATED_SIZES)
    @pytest.mark.parametrize("name", sorted(DERIVED))
    def test_the_published_value_is_inside_the_same_interval(
        self, name: str, subgroup_size: int
    ) -> None:
        """The interval is not so wide that it would accept anything.

        Without this, a band inflated by a mistake in the propagation would
        swallow the printed figure as well as a wrong computation. Asserting
        the published value sits inside it keeps the interval honest, and it
        holds to within the half unit the column is printed to.
        """
        lower, upper = _band(DERIVED[name], subgroup_size)
        published = APPENDIX_VI[subgroup_size][name]
        assert lower - PUBLISHED_PRECISION <= published <= upper + PUBLISHED_PRECISION

    def test_the_individuals_factor_is_consistent_with_the_published_value(self) -> None:
        """E2 = 3/d2 at a span of two, published as 2.660.

        Montgomery (2019), 8th ed., §6.4: individuals limits are
        x_bar +/- E2 * MR_bar. Dividing by a figure known to three decimals
        gives a band of about 0.0024, and the exact 2.6587 and the published
        2.660 both sit inside it.
        """
        lower, upper = _band(lambda d2, _d3, _c4, _n: 3.0 / d2, 2)
        assert lower <= constants.e2(2) <= upper
        assert lower - PUBLISHED_PRECISION <= 2.660 <= upper + PUBLISHED_PRECISION


class TestTheClosedFormsAtTwo:
    """At n = 2 the range is a folded normal and every constant is elementary."""

    def test_the_expected_range_is_two_over_root_pi(self) -> None:
        """The range of two standard normals is |Z| scaled by sqrt(2).

        X1 - X2 has variance 2, and E|N(0, 2)| = sqrt(2) * sqrt(2/pi) =
        2/sqrt(pi) = 1.128379..., which is d2(2) to every digit Appendix VI
        prints and eleven more.
        """
        assert constants.d2(2) == pytest.approx(2.0 / math.sqrt(math.pi), rel=1e-10)

    def test_the_range_standard_deviation_follows_from_the_second_moment(self) -> None:
        """E[W^2] = 2 for two standard normals, so d3(2) = sqrt(2 - 4/pi).

        The second moment of X1 - X2 is its variance, 2, because its mean is
        zero and squaring discards the fold.
        """
        assert constants.d3(2) == pytest.approx(math.sqrt(2.0 - 4.0 / math.pi), rel=1e-10)

    def test_the_bias_factor_is_root_two_over_pi(self) -> None:
        """c4(2) = sqrt(2/pi) directly from the gamma ratio at n = 2."""
        assert constants.c4(2) == pytest.approx(math.sqrt(2.0 / math.pi), rel=1e-12)


class TestTheDefinitionsUnderSampling:
    """Monte Carlo over the definitions, covering sizes beyond the table.

    Verification by simulation per TESTING_STRATEGY.md §3.4: seeded, so the
    result is deterministic, with a tolerance set by the standard error of the
    estimate rather than by what makes the test pass.
    """

    DRAWS = 400_000
    SEED = 20260805

    @pytest.mark.parametrize("subgroup_size", [2, 5, 12, 20, 25])
    def test_d2_is_the_mean_sampled_range(self, subgroup_size: int) -> None:
        """d2 is by definition E[range of n standard normals].

        The mean of 400 000 sampled ranges has standard error d3/sqrt(N),
        about 0.0013 at these sizes; four standard errors is the tolerance.
        """
        generator = np.random.default_rng(self.SEED)
        samples = generator.standard_normal((self.DRAWS, subgroup_size))
        observed = np.ptp(samples, axis=1)
        standard_error = float(np.std(observed, ddof=1)) / math.sqrt(self.DRAWS)
        assert constants.d2(subgroup_size) == pytest.approx(
            float(np.mean(observed)), abs=4.0 * standard_error
        )

    @pytest.mark.parametrize("subgroup_size", [2, 5, 12, 20, 25])
    def test_d3_is_the_sampled_range_standard_deviation(self, subgroup_size: int) -> None:
        """d3 is by definition the standard deviation of that same range.

        A sample standard deviation from N draws has standard error
        approximately sigma/sqrt(2N); four of those is the tolerance.
        """
        generator = np.random.default_rng(self.SEED + 1)
        samples = generator.standard_normal((self.DRAWS, subgroup_size))
        observed = float(np.std(np.ptp(samples, axis=1), ddof=1))
        standard_error = observed / math.sqrt(2.0 * self.DRAWS)
        assert constants.d3(subgroup_size) == pytest.approx(observed, abs=4.0 * standard_error)

    @pytest.mark.parametrize("subgroup_size", [2, 5, 12, 25])
    def test_c4_is_the_mean_sampled_standard_deviation(self, subgroup_size: int) -> None:
        """c4 is E[s]/sigma, which for standard normals is just E[s]."""
        generator = np.random.default_rng(self.SEED + 2)
        samples = generator.standard_normal((self.DRAWS, subgroup_size))
        observed = np.std(samples, axis=1, ddof=1)
        standard_error = float(np.std(observed, ddof=1)) / math.sqrt(self.DRAWS)
        assert constants.c4(subgroup_size) == pytest.approx(
            float(np.mean(observed)), abs=4.0 * standard_error
        )


class TestTheShapeOfTheConstants:
    """Properties that hold across every size, checked where the table stops."""

    @pytest.mark.parametrize("subgroup_size", range(2, 26))
    def test_the_bias_factor_approaches_one_from_below(self, subgroup_size: int) -> None:
        """c4 < 1 always, and rises with n.

        The sample standard deviation understates sigma for any finite n, by
        Jensen's inequality on the square root, and the understatement shrinks.
        """
        corrected = constants.c4(subgroup_size)
        assert 0.0 < corrected < 1.0
        if subgroup_size > constants.MIN_SUBGROUP_SIZE:
            assert corrected > constants.c4(subgroup_size - 1)

    @pytest.mark.parametrize("subgroup_size", range(2, 26))
    def test_the_expected_range_grows_with_the_subgroup(self, subgroup_size: int) -> None:
        """More observations cannot produce a smaller expected range."""
        if subgroup_size > constants.MIN_SUBGROUP_SIZE:
            assert constants.d2(subgroup_size) > constants.d2(subgroup_size - 1)

    @pytest.mark.parametrize("subgroup_size", range(2, 26))
    def test_the_range_chart_has_no_lower_limit_below_seven(self, subgroup_size: int) -> None:
        """D3 is zero for n < 7 and positive from 7 up.

        Montgomery (2019), 8th ed., Appendix VI: 1 - 3*d3/d2 turns positive
        between n = 6 and n = 7, which is why R charts on small subgroups are
        drawn with an upper limit only.
        """
        smallest_with_lower_limit = 7
        lower = constants.d3_lower(subgroup_size)
        if subgroup_size < smallest_with_lower_limit:
            assert lower == 0.0
        else:
            assert lower > 0.0

    @pytest.mark.parametrize("subgroup_size", range(2, 26))
    def test_the_range_limits_straddle_the_centre(self, subgroup_size: int) -> None:
        """D3 < 1 < D4, since the limits multiply the mean range itself."""
        assert constants.d3_lower(subgroup_size) < 1.0 < constants.d4_upper(subgroup_size)


class TestTheRefusals:
    """A constant that cannot be checked against a reference is not returned."""

    @pytest.mark.parametrize("subgroup_size", [1, 0, -3])
    def test_a_subgroup_below_two_is_refused(self, subgroup_size: int) -> None:
        """One observation has no range, so d2 has nothing to average."""
        with pytest.raises(InsufficientDataError):
            constants.d2(subgroup_size)

    def test_a_subgroup_beyond_the_published_table_is_refused(self) -> None:
        """The integral converges above n = 25; the verification does not exist."""
        with pytest.raises(InsufficientDataError):
            constants.d2(constants.MAX_TABULATED_SUBGROUP_SIZE + 1)


class TestTheNormalTailHelpers:
    """The two normal-distribution helpers the ARL work is built on."""

    def test_three_sigma_excludes_the_familiar_proportion(self) -> None:
        """P(|Z| > 3) = 0.0027, whose reciprocal is the in-control ARL of 370.

        Montgomery (2019), 8th ed., §5.3.2.
        """
        assert constants.two_sided_exceedance(3.0) == pytest.approx(0.0027, abs=5e-6)

    def test_the_quantile_inverts_the_exceedance(self) -> None:
        """The quantile at 0.99865 is the 3 sigma bound the exceedance came from."""
        assert constants.normal_quantile(1.0 - 0.0027 / 2.0) == pytest.approx(3.0, abs=1e-3)
