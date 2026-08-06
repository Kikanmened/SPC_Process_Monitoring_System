"""Attribute charts against Montgomery's worked examples and their invariants.

Two published data sets carry most of the weight here. The orange juice can
data (Example 7.1) is the standard p chart example and has a constant sample
size, so its limits can be checked against a single published pair. The printed
circuit board data (Example 7.3) is the standard c chart example. The varying
sample size cases have no published table to check against, so they are checked
against the constant-size cases they must reduce to, which is the stronger test
anyway.

References
----------
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., Table 7.1 and Example 7.1 (p chart), Table 7.7 and Example 7.3
(c chart), §7.2-7.3.
Laney, D. B. (2002). "Improved Control Charts for Attributes." *Quality
Engineering* 14(4), 531-537.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from spc_platform.analytics.charts.attributes import (
    AttributeCounts,
    AttributeDesign,
    AttributeStudy,
    c_study,
    dispersion_ratio,
    np_study,
    p_study,
    u_study,
)
from spc_platform.analytics.charts.panels import PanelIdentity
from spc_platform.common.errors import (
    ConfigurationError,
    DegenerateSeriesError,
    InsufficientDataError,
    UnsupportedChartError,
)
from spc_platform.common.types import IntArray
from spc_platform.domain.enums import ChartStatistic, ChartType, SigmaEstimator
from spc_platform.domain.ids import BaselineId, ParameterId, UnitSymbol

ORANGE_JUICE_DEFECTIVES = (
    12, 15, 8, 10, 4, 7, 16, 9, 14, 10,
    5, 6, 17, 12, 22, 8, 10, 5, 13, 11,
    20, 18, 24, 15, 9, 12, 7, 13, 9, 6,
)  # fmt: skip
"""Montgomery Table 7.1: 30 samples of 50 cans, 347 defective in total."""

ORANGE_JUICE_SIZE = 50
PUBLISHED_P_BAR = 0.2313
PUBLISHED_P_UCL = 0.4102
PUBLISHED_P_LCL = 0.0524

CIRCUIT_BOARD_DEFECTS = (
    21, 24, 16, 12, 15, 5, 28, 20, 31, 25,
    20, 24, 16, 19, 10, 17, 13, 22, 18, 39,
    30, 24, 16, 19, 17, 15,
)  # fmt: skip
"""Montgomery Table 7.7: 26 boards, 516 defects in total."""

PUBLISHED_C_BAR = 19.85
PUBLISHED_C_UCL = 33.22
PUBLISHED_C_LCL = 6.48


def counts(
    events: tuple[int, ...],
    opportunity: float | tuple[float, ...],
) -> AttributeCounts:
    """Wrap counts and inspection sizes as points one hour apart."""
    sizes = (
        np.full(len(events), opportunity, dtype=np.float64)
        if isinstance(opportunity, int | float)
        else np.array(opportunity, dtype=np.float64)
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return AttributeCounts(
        events=np.array(events, dtype=np.int_),
        opportunity=sizes,
        timestamps=tuple(start + timedelta(hours=i) for i in range(len(events))),
    )


def identity() -> PanelIdentity:
    """Name the parameter and baseline an attribute chart is drawn for."""
    return PanelIdentity(
        parameter_id=ParameterId("nonconforming"),
        baseline_id=BaselineId("baseline-1"),
        chart_type=ChartType.P,
        statistic=ChartStatistic.PROPORTION_DEFECTIVE,
        unit=UnitSymbol("count"),
    )


class TestTheMontgomeryPChart:
    """Example 7.1: 30 samples of 50 orange juice cans."""

    @pytest.fixture
    def study(self) -> AttributeStudy:
        """Fit a p chart to the published counts."""
        return p_study(counts(ORANGE_JUICE_DEFECTIVES, ORANGE_JUICE_SIZE), identity())

    def test_the_centre_line_is_the_published_rate(self, study: AttributeStudy) -> None:
        """p-bar = 347 / 1500 = 0.2313."""
        assert study.total_events == 347
        assert study.centre_line == pytest.approx(PUBLISHED_P_BAR, abs=5e-5)

    def test_the_limits_match_the_published_pair(self, study: AttributeStudy) -> None:
        """UCL = 0.4102 and LCL = 0.0524, from a constant sample size of 50."""
        assert study.panel.limits.ucl is not None
        assert study.panel.limits.lcl is not None
        assert study.panel.limits.ucl[0] == pytest.approx(PUBLISHED_P_UCL, abs=5e-5)
        assert study.panel.limits.lcl[0] == pytest.approx(PUBLISHED_P_LCL, abs=5e-5)

    def test_the_plotted_points_are_fractions(self, study: AttributeStudy) -> None:
        """Sample 15 had 22 of 50 defective, a fraction of 0.44."""
        assert study.panel.series.values[14] == pytest.approx(0.44)

    def test_the_chart_names_the_binomial_as_its_spread(self, study: AttributeStudy) -> None:
        """The spread was not estimated; it follows from the centre line."""
        assert study.panel.limits.sigma_estimator is SigmaEstimator.BINOMIAL

    def test_the_published_signals_are_found(self, study: AttributeStudy) -> None:
        """Montgomery finds samples 15 and 23 above the upper limit."""
        assert study.panel.limits.ucl is not None
        values = np.asarray(study.panel.series.values)
        above = np.flatnonzero(values > np.asarray(study.panel.limits.ucl))
        assert [int(index) + 1 for index in above] == [15, 23]


class TestTheMontgomeryCChart:
    """Example 7.3: 26 printed circuit boards, 516 defects."""

    @pytest.fixture
    def study(self) -> AttributeStudy:
        """Fit a c chart to the published counts."""
        return c_study(counts(CIRCUIT_BOARD_DEFECTS, 1.0), identity())

    def test_the_centre_line_is_the_published_mean(self, study: AttributeStudy) -> None:
        """c-bar = 516 / 26 = 19.85."""
        assert study.total_events == 516
        assert study.centre_line == pytest.approx(PUBLISHED_C_BAR, abs=5e-3)

    def test_the_limits_are_exactly_three_root_c_bar(self, study: AttributeStudy) -> None:
        """The limits follow from the centre line with nothing else estimated."""
        exact = 516.0 / 26.0
        assert study.panel.limits.ucl is not None
        assert study.panel.limits.lcl is not None
        assert study.panel.limits.ucl[0] == pytest.approx(exact + 3.0 * np.sqrt(exact))
        assert study.panel.limits.lcl[0] == pytest.approx(exact - 3.0 * np.sqrt(exact))

    def test_the_limits_agree_with_the_published_pair(self, study: AttributeStudy) -> None:
        """UCL = 33.22 and LCL = 6.48, within the table's own rounding.

        Montgomery derives both from c-bar rounded to 19.85, not from the exact
        516/26 = 19.8462. Half a unit in the last published place of the centre
        line moves the limit by ``1 + 3 / (2 sqrt(c-bar))`` times as much, and
        the limit is itself quoted to two decimals. Comparing to the published
        figure any tighter than that band would be testing Montgomery's
        typesetter rather than this code.
        """
        exact = 516.0 / 26.0
        centre_rounding = 0.005
        band = centre_rounding * (1.0 + 3.0 / (2.0 * np.sqrt(exact))) + 0.005

        assert study.panel.limits.ucl is not None
        assert study.panel.limits.lcl is not None
        assert study.panel.limits.ucl[0] == pytest.approx(PUBLISHED_C_UCL, abs=band)
        assert study.panel.limits.lcl[0] == pytest.approx(PUBLISHED_C_LCL, abs=band)

    def test_the_published_signals_are_found(self, study: AttributeStudy) -> None:
        """Montgomery finds boards 6 and 20 outside the limits."""
        assert study.panel.limits.ucl is not None
        assert study.panel.limits.lcl is not None
        values = np.asarray(study.panel.series.values)
        outside = (values > np.asarray(study.panel.limits.ucl)) | (
            values < np.asarray(study.panel.limits.lcl)
        )
        assert [int(index) + 1 for index in np.flatnonzero(outside)] == [6, 20]

    def test_the_chart_names_the_poisson_as_its_spread(self, study: AttributeStudy) -> None:
        """One parameter, so the centre line determines the limits entirely."""
        assert study.panel.limits.sigma_estimator is SigmaEstimator.POISSON


class TestTheChartsAgree:
    """Each pair of charts is the same model, differently scaled.

    These are the tests that catch an arithmetic slip in the varying-size case,
    which has no published table to check against.
    """

    def test_np_is_p_multiplied_by_the_sample_size(self) -> None:
        """The two charts must signal on exactly the same points."""
        data = counts(ORANGE_JUICE_DEFECTIVES, ORANGE_JUICE_SIZE)
        proportion = p_study(data, identity())
        number = np_study(data, identity())

        assert number.centre_line == pytest.approx(proportion.centre_line * ORANGE_JUICE_SIZE)
        assert proportion.panel.limits.ucl is not None
        assert number.panel.limits.ucl is not None
        assert number.panel.limits.ucl[0] == pytest.approx(
            proportion.panel.limits.ucl[0] * ORANGE_JUICE_SIZE
        )

    def test_u_reduces_to_c_at_one_inspection_unit(self) -> None:
        """With one unit inspected per point, defects per unit is just defects."""
        data = counts(CIRCUIT_BOARD_DEFECTS, 1.0)
        per_unit = u_study(data, identity())
        raw = c_study(data, identity())

        assert per_unit.centre_line == pytest.approx(raw.centre_line)
        assert per_unit.panel.limits.ucl is not None
        assert raw.panel.limits.ucl is not None
        assert per_unit.panel.limits.ucl[0] == pytest.approx(raw.panel.limits.ucl[0])

    def test_larger_samples_get_tighter_limits(self) -> None:
        """The whole reason limits are computed per point rather than once.

        Drawing every point against the average sample size would make the
        large samples look stable when they are not.
        """
        data = counts((5, 5, 50, 50), (100.0, 100.0, 1000.0, 1000.0))
        study = p_study(data, identity())
        upper = study.panel.limits.ucl
        assert upper is not None
        assert upper[2] < upper[0], "ten times the sample, tighter limits"

    def test_the_limits_scale_as_the_root_of_the_sample_size(self) -> None:
        """Ten times the sample narrows the limit by the square root of ten."""
        data = counts((5, 5, 50, 50), (100.0, 100.0, 1000.0, 1000.0))
        study = p_study(data, identity())
        upper = study.panel.limits.ucl
        assert upper is not None
        wide = upper[0] - study.centre_line
        narrow = upper[2] - study.centre_line
        assert wide / narrow == pytest.approx(np.sqrt(10.0), rel=1e-9)


class TestTheDispersionCheck:
    """Whether the counts behave the way the assumed distribution requires."""

    def test_binomial_data_reports_a_ratio_near_one(self) -> None:
        """Counts drawn from the assumed distribution should not look unusual."""
        rng = np.random.default_rng(20260803)
        drawn = rng.binomial(200, 0.05, 300)
        study = p_study(counts(tuple(int(value) for value in drawn), 200.0), identity())
        assert study.dispersion.ratio == pytest.approx(1.0, abs=0.15)
        assert not study.dispersion.is_overdispersed
        assert not study.dispersion.is_underdispersed

    def test_clustered_defects_are_flagged_as_overdispersed(self) -> None:
        """Defects that cluster vary far more than the Poisson permits.

        This is the normal case for a fab, and the reason a c chart drawn from
        theoretical limits alone signals on nearly every point.
        """
        rng = np.random.default_rng(20260803)
        clustered = rng.negative_binomial(2, 2.0 / 22.0, 200)
        study = c_study(counts(tuple(int(value) for value in clustered), 1.0), identity())
        assert study.dispersion.is_overdispersed
        assert study.dispersion.ratio > 1.2

    def test_the_correction_is_not_applied_unless_asked(self) -> None:
        """A chart whose limits were widened to stop it complaining is a claim."""
        rng = np.random.default_rng(20260803)
        clustered = rng.negative_binomial(2, 2.0 / 22.0, 200)
        data = counts(tuple(int(value) for value in clustered), 1.0)

        plain = c_study(data, identity())
        assert not plain.dispersion.applied
        assert plain.panel.limits.sigma_estimator is SigmaEstimator.POISSON

    def test_the_correction_widens_the_limits_and_says_so(self) -> None:
        """Laney's correction scales the standard error by the observed ratio."""
        rng = np.random.default_rng(20260803)
        clustered = rng.negative_binomial(2, 2.0 / 22.0, 200)
        data = counts(tuple(int(value) for value in clustered), 1.0)

        plain = c_study(data, identity())
        corrected = c_study(data, identity(), AttributeDesign(laney_correction=True))

        assert corrected.dispersion.applied
        assert corrected.panel.limits.sigma_estimator is SigmaEstimator.LANEY
        assert plain.panel.limits.ucl is not None
        assert corrected.panel.limits.ucl is not None
        assert corrected.panel.limits.ucl[0] > plain.panel.limits.ucl[0]

    def test_the_correction_leaves_well_behaved_data_almost_alone(self) -> None:
        """On data the distribution fits, the ratio is one and nothing moves."""
        rng = np.random.default_rng(20260803)
        drawn = rng.binomial(200, 0.05, 300)
        data = counts(tuple(int(value) for value in drawn), 200.0)

        plain = p_study(data, identity())
        corrected = p_study(data, identity(), AttributeDesign(laney_correction=True))

        assert plain.panel.limits.ucl is not None
        assert corrected.panel.limits.ucl is not None
        assert corrected.panel.limits.ucl[0] == pytest.approx(plain.panel.limits.ucl[0], rel=0.15)

    def test_a_sustained_shift_does_not_inflate_the_ratio(self) -> None:
        """The moving range estimator is what makes the check trustworthy.

        A plain standard deviation of the standardised points would absorb this
        step into the dispersion estimate and widen the limits until the step
        stopped signalling — the exact failure the chart exists to prevent.
        """
        rng = np.random.default_rng(20260803)
        before = rng.binomial(200, 0.05, 150)
        after = rng.binomial(200, 0.10, 150)
        drawn = np.concatenate([before, after])

        study = p_study(counts(tuple(int(value) for value in drawn), 200.0), identity())
        naive = float(
            np.std(
                (np.asarray(study.panel.series.values) - study.centre_line)
                / np.asarray(study.panel.limits.sigma_statistic),
                ddof=1,
            )
        )
        assert study.dispersion.ratio < naive
        assert study.dispersion.ratio == pytest.approx(1.0, abs=0.25)

    def test_the_ratio_is_one_for_exactly_standard_variation(self) -> None:
        """A hand-checkable case: standardised points alternating by two.

        Mean moving range is 2, and 2 / d2(2) = 2 / 1.128 = 1.7734.
        """
        plotted = np.array([1.0, -1.0, 1.0, -1.0, 1.0])
        ratio = dispersion_ratio(plotted, 0.0, np.array([1.0]))
        assert ratio == pytest.approx(2.0 / 1.128379167, rel=1e-6)


class TestTheRefusals:
    """What each chart will not draw, and what it says instead."""

    def test_np_refuses_a_varying_sample_size(self) -> None:
        """A raw count only compares across points when the size is constant."""
        with pytest.raises(UnsupportedChartError, match="p chart"):
            np_study(counts((5, 6, 7), (100.0, 200.0, 100.0)), identity())

    def test_c_refuses_a_varying_opportunity(self) -> None:
        """A count of defects has to be over the same area at every point."""
        with pytest.raises(UnsupportedChartError, match="u chart"):
            c_study(counts((5, 6, 7), (1.0, 2.0, 1.0)), identity())

    def test_a_flawless_process_is_refused(self) -> None:
        """Zero defectives gives zero-width limits and infinite sensitivity."""
        with pytest.raises(DegenerateSeriesError, match="rare-event"):
            p_study(counts((0, 0, 0, 0), 100.0), identity())

    def test_a_wholly_defective_process_is_refused(self) -> None:
        """The upper edge collapses the limits the same way the lower one does."""
        with pytest.raises(DegenerateSeriesError):
            p_study(counts((100, 100, 100), 100.0), identity())

    def test_more_defectives_than_units_is_refused(self) -> None:
        """A defective unit is a unit, so the count cannot exceed the sample."""
        with pytest.raises(ConfigurationError, match="defective than were inspected"):
            p_study(counts((5, 150, 7), 100.0), identity())

    def test_defects_may_exceed_the_units_inspected(self) -> None:
        """One board can carry many defects, which is the point of a c chart."""
        study = c_study(counts((5, 150, 7), 1.0), identity())
        assert study.total_events == 162

    def test_a_negative_count_is_refused(self) -> None:
        """Nothing was un-found."""
        events: IntArray = np.array([5, -1, 7], dtype=np.int_)
        data = counts((5, 1, 7), 100.0)
        with pytest.raises(ConfigurationError, match="cannot be negative"):
            p_study(
                AttributeCounts(
                    events=events,
                    opportunity=data.opportunity,
                    timestamps=data.timestamps,
                ),
                identity(),
            )

    def test_an_empty_inspection_is_refused(self) -> None:
        """A point that inspected nothing has an undefined rate."""
        with pytest.raises(ConfigurationError, match="inspected something"):
            u_study(counts((5, 6, 7), (2.0, 0.0, 2.0)), identity())

    def test_a_single_point_is_refused(self) -> None:
        """A rate estimated from one sample is that sample."""
        with pytest.raises(InsufficientDataError):
            p_study(counts((5,), 100.0), identity())

    def test_mismatched_lengths_are_refused(self) -> None:
        """Counts, opportunities, and timestamps describe the same points."""
        data = counts((5, 6, 7), 100.0)
        with pytest.raises(InsufficientDataError, match="line up"):
            p_study(
                AttributeCounts(
                    events=data.events,
                    opportunity=data.opportunity[:-1],
                    timestamps=data.timestamps,
                ),
                identity(),
            )
