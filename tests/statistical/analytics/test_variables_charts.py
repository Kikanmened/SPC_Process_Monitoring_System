"""Variables charts against published worked examples.

Montgomery's piston ring data is the canonical X-bar/R example and is
reproduced from the published summary statistics rather than from the raw
table: the book prints x_bar_bar, R_bar, and the resulting limits, and those
are what a reader can check. Where a raw dataset is needed, it is the
NIST/SEMATECH one, quoted in the docstring of the test that uses it.

The chart code computes limits as three standard errors of the plotted
statistic rather than by applying A2, D3, D4, B3, and B4. That is the same
arithmetic, and the equivalence is asserted here rather than assumed — it is
what allows a configured sigma multiplier other than three, which the factor
tables cannot express.
"""

from __future__ import annotations

from typing import ClassVar

import numpy as np
import pytest

from spc_platform.analytics.charts import variables
from spc_platform.analytics.charts.study import ChartStudy
from spc_platform.analytics.estimators import constants
from spc_platform.common.errors import DegenerateSeriesError, InsufficientDataError
from spc_platform.common.types import FloatMatrix
from spc_platform.domain.enums import ChartStatistic, SigmaEstimator

pytestmark = pytest.mark.statistical


# Montgomery (2019), 8th ed., Table 6.1: piston ring inside diameter, 25
# subgroups of 5, in millimetres. The book's summary statistics for this table
# are x_bar_bar = 74.001 and R_bar = 0.023.
PISTON_RING_GRAND_MEAN = 74.001
PISTON_RING_MEAN_RANGE = 0.023
PISTON_RING_SUBGROUP_SIZE = 5


def _subgroups_with(grand_mean: float, mean_range: float, size: int, count: int) -> FloatMatrix:
    """Build subgroups with exactly the requested grand mean and mean range.

    A subgroup of ``size`` values placed symmetrically about the mean, with its
    extremes ``mean_range`` apart, has that range exactly and that mean
    exactly. Repeating it ``count`` times gives a matrix whose summary
    statistics are the published ones to machine precision, which is what lets
    the published limits be checked without the raw table.
    """
    interior = np.linspace(-0.5, 0.5, size)
    return np.tile(grand_mean + interior * mean_range, (count, 1))


class TestTheXbarRExample:
    """Montgomery's piston ring X-bar/R limits."""

    @pytest.fixture
    def study(self) -> ChartStudy:
        """Build a study whose summary statistics are the published ones."""
        subgroups = _subgroups_with(
            PISTON_RING_GRAND_MEAN, PISTON_RING_MEAN_RANGE, PISTON_RING_SUBGROUP_SIZE, 25
        )
        return variables.xbar_r_study(subgroups)

    def test_the_summary_statistics_are_the_published_ones(self, study: ChartStudy) -> None:
        """The constructed data reproduces x_bar_bar = 74.001 and R_bar = 0.023.

        Asserted first, because every limit below is a function of these two
        and a test that skipped this would be checking arithmetic on the wrong
        inputs.
        """
        assert study.location.centre_line == pytest.approx(PISTON_RING_GRAND_MEAN)
        assert study.dispersion is not None
        assert study.dispersion.centre_line == pytest.approx(PISTON_RING_MEAN_RANGE)

    def test_the_mean_limits_match_the_published_values(self, study: ChartStudy) -> None:
        """X-bar limits for the piston ring data.

        Montgomery (2019), 8th ed., Example 6.1: with x_bar_bar = 74.001,
        R_bar = 0.023 and A2 = 0.577 for n = 5, the published limits are
        UCL = 74.014 and LCL = 73.988.
        """
        expected_reach = constants.a2(PISTON_RING_SUBGROUP_SIZE) * PISTON_RING_MEAN_RANGE
        assert study.location.ucl == pytest.approx(
            PISTON_RING_GRAND_MEAN + expected_reach, abs=5e-4
        )
        assert study.location.lcl == pytest.approx(
            PISTON_RING_GRAND_MEAN - expected_reach, abs=5e-4
        )
        assert study.location.ucl == pytest.approx(74.014, abs=5e-4)
        assert study.location.lcl == pytest.approx(73.988, abs=5e-4)

    def test_the_range_limits_match_the_published_values(self, study: ChartStudy) -> None:
        """R chart limits for the piston ring data.

        Montgomery (2019), 8th ed., Example 6.1: D3 = 0 and D4 = 2.114 at
        n = 5, giving UCL = 2.114 * 0.023 = 0.04862 and no lower limit.
        """
        assert study.dispersion is not None
        assert study.dispersion.ucl == pytest.approx(
            constants.d4_upper(PISTON_RING_SUBGROUP_SIZE) * PISTON_RING_MEAN_RANGE, rel=1e-9
        )
        assert study.dispersion.ucl == pytest.approx(0.04862, abs=5e-5)
        assert study.dispersion.lcl == 0.0
        assert study.dispersion.has_lower_limit is False

    def test_the_sigma_estimate_names_its_estimator(self, study: ChartStudy) -> None:
        """R_bar/d2 = 0.023/2.326 = 0.00989, tagged as the estimator used.

        Montgomery (2019), 8th ed., Example 6.1 reports sigma_hat = 0.0099.
        """
        assert study.sigma_within.estimator is SigmaEstimator.R_BAR_D2
        assert study.sigma_within.value == pytest.approx(
            PISTON_RING_MEAN_RANGE / constants.d2(PISTON_RING_SUBGROUP_SIZE), rel=1e-9
        )
        assert study.sigma_within.value == pytest.approx(0.0099, abs=5e-5)


class TestTheFactorEquivalence:
    """The general form reproduces the published factors exactly at three sigma.

    This is the check that lets the chart code use standard errors rather than
    table lookups. If the two ever disagree, one of them is wrong, and the
    factors are the ones with a published table behind them.
    """

    SIZES: ClassVar[list[int]] = list(range(2, 11))

    @pytest.mark.parametrize("subgroup_size", SIZES)
    def test_the_mean_limits_equal_a2_times_the_mean_range(self, subgroup_size: int) -> None:
        """3 * sigma_hat / sqrt(n) is A2 * R_bar, by the definition of A2."""
        subgroups = _subgroups_with(100.0, 4.0, subgroup_size, 20)
        study = variables.xbar_r_study(subgroups)
        mean_range = 4.0
        assert study.location.ucl - study.location.centre_line == pytest.approx(
            constants.a2(subgroup_size) * mean_range, rel=1e-12
        )

    @pytest.mark.parametrize("subgroup_size", SIZES)
    def test_the_range_limits_equal_the_d_factors(self, subgroup_size: int) -> None:
        """The range panel reproduces D3 * R_bar and D4 * R_bar."""
        subgroups = _subgroups_with(100.0, 4.0, subgroup_size, 20)
        study = variables.xbar_r_study(subgroups)
        assert study.dispersion is not None
        assert study.dispersion.ucl == pytest.approx(
            constants.d4_upper(subgroup_size) * 4.0, rel=1e-12
        )
        assert study.dispersion.lcl == pytest.approx(
            constants.d3_lower(subgroup_size) * 4.0, rel=1e-12
        )

    @pytest.mark.parametrize("subgroup_size", SIZES)
    def test_the_stdev_limits_equal_the_b_factors(self, subgroup_size: int) -> None:
        """The s panel reproduces B3 * s_bar and B4 * s_bar."""
        generator = np.random.default_rng(20260805)
        subgroups = generator.normal(50.0, 2.0, (30, subgroup_size))
        study = variables.xbar_s_study(subgroups)
        assert study.dispersion is not None
        mean_stdev = study.dispersion.centre_line
        assert study.dispersion.ucl == pytest.approx(
            constants.b4(subgroup_size) * mean_stdev, rel=1e-12
        )
        assert study.dispersion.lcl == pytest.approx(
            constants.b3(subgroup_size) * mean_stdev, rel=1e-12
        )

    @pytest.mark.parametrize("subgroup_size", SIZES)
    def test_the_mean_limits_equal_a3_times_the_mean_stdev(self, subgroup_size: int) -> None:
        """The X-bar panel of an X-bar/S chart reproduces A3 * s_bar."""
        generator = np.random.default_rng(20260806)
        subgroups = generator.normal(50.0, 2.0, (30, subgroup_size))
        study = variables.xbar_s_study(subgroups)
        assert study.dispersion is not None
        assert study.location.ucl - study.location.centre_line == pytest.approx(
            constants.a3(subgroup_size) * study.dispersion.centre_line, rel=1e-12
        )


class TestTheIndividualsChart:
    """I-MR limits, where the moving range replaces the subgroup."""

    def test_the_limits_are_e2_times_the_mean_moving_range(self) -> None:
        """Individuals limits are x_bar +/- E2 * MR_bar with E2 = 2.660.

        Montgomery (2019), 8th ed., §6.4, Equation 6.25. Written here as
        3 * MR_bar / d2(2), which is what E2 abbreviates.
        """
        values = np.array([10.0, 12.0, 11.0, 13.0, 12.0, 10.0, 11.0, 14.0])
        study = variables.individuals_study(values)
        mean_moving_range = study.dispersion.centre_line if study.dispersion else 0.0
        reach = study.location.ucl - study.location.centre_line
        assert reach == pytest.approx(constants.e2(2) * mean_moving_range, rel=1e-12)

    def test_the_moving_range_panel_has_no_lower_limit(self) -> None:
        """D3 is zero at a span of two, so the MR chart has an upper limit only."""
        values = np.array([10.0, 12.0, 11.0, 13.0, 12.0, 10.0, 11.0, 14.0])
        study = variables.individuals_study(values)
        assert study.dispersion is not None
        assert study.dispersion.lcl == 0.0
        assert study.dispersion.has_lower_limit is False
        assert study.dispersion.ucl == pytest.approx(
            constants.d4_upper(2) * study.dispersion.centre_line, rel=1e-12
        )

    def test_the_estimate_uses_the_moving_range_not_the_overall_spread(self) -> None:
        """A trend inflates the overall spread and must not inflate the limits.

        A perfectly linear ramp has a constant moving range, so the short-term
        estimate is small and every later point is far outside the limits. The
        overall standard deviation of the same data is several times larger,
        and using it would produce a chart on which a textbook trend passes
        without comment. Hand-computed: steps of 1.0 give MR_bar = 1.0 and
        sigma_within = 1/1.128 = 0.8865, against an overall sigma of 6.06.
        """
        ramp = np.arange(20.0)
        study = variables.individuals_study(ramp)
        assert study.sigma_within.estimator is SigmaEstimator.MR_BAR_D2
        assert study.sigma_within.value == pytest.approx(1.0 / constants.d2(2), rel=1e-12)
        assert float(np.std(ramp, ddof=1)) > 5.0 * study.sigma_within.value


class TestTheConfiguredMultiplier:
    """A sigma multiplier other than three is honoured on every panel."""

    def test_two_sigma_limits_are_two_thirds_as_wide(self) -> None:
        """Limit width is proportional to the multiplier, on both panels."""
        subgroups = _subgroups_with(100.0, 4.0, 5, 20)
        three = variables.xbar_r_study(subgroups, sigma_multiplier=3.0)
        two = variables.xbar_r_study(subgroups, sigma_multiplier=2.0)
        three_reach = three.location.ucl - three.location.centre_line
        two_reach = two.location.ucl - two.location.centre_line
        assert two_reach == pytest.approx(three_reach * 2.0 / 3.0, rel=1e-12)

    def test_a_narrow_multiplier_gives_the_range_chart_a_lower_limit(self) -> None:
        """At n = 5 the R chart gains a lower limit once the multiplier drops.

        D3 is zero at three sigma because 3 * d3/d2 exceeds one. At two sigma
        it does not, so a lower limit exists and is reachable — a fact the
        factor tables cannot express, since they are tabulated at three sigma.
        """
        subgroups = _subgroups_with(100.0, 4.0, 5, 20)
        narrow = variables.xbar_r_study(subgroups, sigma_multiplier=2.0)
        assert narrow.dispersion is not None
        assert narrow.dispersion.has_lower_limit is True
        assert narrow.dispersion.lcl > 0.0


class TestTheRefusals:
    """What the study does when the data cannot support one."""

    def test_a_constant_series_is_refused(self) -> None:
        """Zero spread would give zero-width limits and signal on everything."""
        with pytest.raises(DegenerateSeriesError):
            variables.individuals_study(np.full(10, 7.0))

    def test_constant_subgroups_are_refused(self) -> None:
        """The same, one subgroup at a time."""
        with pytest.raises(DegenerateSeriesError):
            variables.xbar_r_study(np.full((10, 5), 7.0))

    def test_a_single_subgroup_is_refused(self) -> None:
        """One subgroup gives a centre line and no sense of its uncertainty."""
        with pytest.raises(InsufficientDataError):
            variables.xbar_r_study(np.array([[1.0, 2.0, 3.0]]))

    def test_a_single_observation_is_refused(self) -> None:
        """One value has no neighbour and so no moving range."""
        with pytest.raises(InsufficientDataError):
            variables.individuals_study(np.array([1.0]))


class TestTheStatisticsPlotted:
    """Each panel plots the statistic it says it does."""

    def test_the_xbar_r_panels_are_named_correctly(self) -> None:
        """Location plots subgroup means, dispersion plots ranges."""
        study = variables.xbar_r_study(_subgroups_with(100.0, 4.0, 5, 20))
        assert study.location.statistic is ChartStatistic.SUBGROUP_MEAN
        assert study.dispersion is not None
        assert study.dispersion.statistic is ChartStatistic.SUBGROUP_RANGE

    def test_the_xbar_s_panels_are_named_correctly(self) -> None:
        """Location plots subgroup means, dispersion plots standard deviations."""
        generator = np.random.default_rng(20260807)
        study = variables.xbar_s_study(generator.normal(50.0, 2.0, (30, 8)))
        assert study.location.statistic is ChartStatistic.SUBGROUP_MEAN
        assert study.dispersion is not None
        assert study.dispersion.statistic is ChartStatistic.SUBGROUP_STDEV

    def test_the_individuals_panels_are_named_correctly(self) -> None:
        """Location plots individuals, dispersion plots moving ranges."""
        study = variables.individuals_study(np.array([1.0, 3.0, 2.0, 5.0, 4.0]))
        assert study.location.statistic is ChartStatistic.INDIVIDUAL
        assert study.dispersion is not None
        assert study.dispersion.statistic is ChartStatistic.MOVING_RANGE
