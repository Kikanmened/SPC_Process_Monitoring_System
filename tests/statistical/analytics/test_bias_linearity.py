"""Bias, linearity, and stability against hand-computable cases and known truth.

Gauge R&R says how much a gauge scatters. These say whether it points at the
right place, and a gauge can pass one and fail the other completely: perfect
repeatability with a constant 3 nm offset is invisible to every chart and every
capability index in this platform until someone measures the same part on a
different tool.

References
----------
NIST/SEMATECH e-Handbook of Statistical Methods, §2.3.3 (bias and linearity),
§2.2.3 (control of the measurement process).
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §8.7.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest
from scipy import stats

from spc_platform.analytics.msa.bias_linearity import bias, linearity
from spc_platform.analytics.msa.stability import stability
from spc_platform.common.errors import (
    ConfigurationError,
    DegenerateSeriesError,
    InsufficientDataError,
)

WINDOW = (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 3, 31, tzinfo=UTC))


class TestBias:
    """A one-sample t-test of the gauge against a calibrated standard."""

    def test_the_offset_is_the_mean_minus_the_reference(self) -> None:
        """Signed, so the sign says which way the gauge reads."""
        measurements = np.array([10.2, 10.4, 10.1, 10.3, 10.5])
        result = bias(measurements, 10.0)
        assert result.bias == pytest.approx(0.3)
        assert result.mean_measurement == pytest.approx(10.3)

    def test_the_statistic_matches_the_textbook_formula(self) -> None:
        """The statistic is (x-bar - reference) / (s / sqrt(n)), computed independently."""
        measurements = np.array([10.2, 10.4, 10.1, 10.3, 10.5])
        result = bias(measurements, 10.0)

        expected = (np.mean(measurements) - 10.0) / (
            np.std(measurements, ddof=1) / np.sqrt(measurements.size)
        )
        assert result.t_statistic == pytest.approx(expected)
        assert result.degrees_of_freedom == 4

    def test_the_p_value_agrees_with_scipy(self) -> None:
        """An independent implementation of the same two-sided test."""
        measurements = np.array([10.2, 10.4, 10.1, 10.3, 10.5])
        result = bias(measurements, 10.0)
        reference = stats.ttest_1samp(measurements, 10.0)
        assert result.p_value == pytest.approx(float(reference.pvalue))

    def test_a_real_offset_is_detected(self) -> None:
        """Twenty measurements half a sigma off the standard, consistently."""
        rng = np.random.default_rng(20260803)
        measurements = rng.normal(10.5, 0.1, 20)
        result = bias(measurements, 10.0)
        assert result.is_significant
        assert result.bias == pytest.approx(0.5, abs=0.1)

    def test_an_unbiased_gauge_is_not_flagged(self) -> None:
        """Measurements scattered around the standard should not raise an alarm."""
        rng = np.random.default_rng(20260803)
        result = bias(rng.normal(10.0, 0.1, 30), 10.0)
        assert not result.is_significant

    def test_the_interval_brackets_the_estimate(self) -> None:
        """And excludes zero exactly when the test rejects it."""
        rng = np.random.default_rng(20260803)
        result = bias(rng.normal(10.5, 0.1, 20), 10.0)
        lower, upper = result.confidence_interval
        assert lower < result.bias < upper
        assert lower > 0.0
        assert result.is_significant

    def test_the_interval_covers_zero_for_an_unbiased_gauge(self) -> None:
        """The interval and the verdict must agree, or one of them is wrong."""
        rng = np.random.default_rng(20260803)
        result = bias(rng.normal(10.0, 0.1, 30), 10.0)
        lower, upper = result.confidence_interval
        assert lower < 0.0 < upper
        assert not result.is_significant

    def test_a_perfectly_repeatable_gauge_is_refused(self) -> None:
        """Identical readings give a zero standard error and an infinite statistic.

        This is not a contrived case — a gauge quantising coarsely relative to
        its own noise produces exactly this — and returning infinity would
        report the strongest possible evidence of bias from a gauge that may
        have none.
        """
        with pytest.raises(DegenerateSeriesError):
            bias(np.full(10, 10.0), 10.0)

    def test_a_single_measurement_is_refused(self) -> None:
        """One reading has no standard error."""
        with pytest.raises(InsufficientDataError):
            bias(np.array([10.0]), 10.0)

    @pytest.mark.parametrize("significance", [0.0, 1.0, -0.1, 1.5])
    def test_an_impossible_significance_is_refused(self, significance: float) -> None:
        """A significance level is a probability."""
        with pytest.raises(ConfigurationError):
            bias(np.array([10.0, 10.2, 10.1]), 10.0, significance=significance)


class TestLinearity:
    """Whether the bias stays constant across the gauge's operating range."""

    def test_a_constant_bias_gives_no_slope(self) -> None:
        """The gauge reads 0.5 high everywhere, which is a calibration problem."""
        references = np.array([2.0, 2.0, 4.0, 4.0, 6.0, 6.0, 8.0, 8.0])
        measurements = (
            references + 0.5 + np.array([0.01, -0.01, 0.02, -0.02, 0.01, -0.01, 0.02, -0.02])
        )
        result = linearity(references, measurements)
        assert result.slope == pytest.approx(0.0, abs=1e-2)
        assert result.is_linear
        assert result.intercept == pytest.approx(0.5, abs=1e-2)

    def test_a_proportional_error_gives_a_slope(self) -> None:
        """A gauge reading 5% high has a bias that grows with the magnitude.

        This is the case a bias study run only at nominal cannot find, and the
        one that fails every part at the specification limit.
        """
        references = np.array([2.0, 2.0, 4.0, 4.0, 6.0, 6.0, 8.0, 8.0])
        measurements = references * 1.05 + np.array(
            [0.01, -0.01, 0.02, -0.02, 0.01, -0.01, 0.02, -0.02]
        )
        result = linearity(references, measurements)
        assert result.slope == pytest.approx(0.05, abs=5e-3)
        assert not result.is_linear
        assert result.r_squared > 0.95

    def test_the_fit_agrees_with_scipy(self) -> None:
        """The regression is of bias on reference, not measurement on reference."""
        references = np.array([2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
        measurements = np.array([2.1, 3.0, 4.3, 5.2, 6.6, 7.4])
        result = linearity(references, measurements)

        reference_fit = stats.linregress(references, measurements - references)
        assert result.slope == pytest.approx(float(reference_fit.slope))
        assert result.intercept == pytest.approx(float(reference_fit.intercept))

    def test_the_null_is_a_zero_slope(self) -> None:
        """Regressing bias rather than measurement is what puts the null here.

        Regressing the measurement on the reference would put the null at a
        slope of one, which is the same test arranged so that the interesting
        answer is the one that looks unremarkable.
        """
        references = np.array([2.0, 2.0, 4.0, 4.0, 6.0, 6.0])
        measurements = references + 0.5
        on_measurement = stats.linregress(references, measurements)
        assert on_measurement.slope == pytest.approx(1.0)

        result = linearity(
            references, measurements + np.array([0.01, -0.01, 0.0, 0.0, 0.01, -0.01])
        )
        assert result.slope == pytest.approx(0.0, abs=1e-2)
        assert result.is_linear

    def test_linearity_is_the_slope_over_the_working_range(self) -> None:
        """A steep slope over a narrow range may matter less than a shallow one."""
        references = np.array([2.0, 2.0, 4.0, 4.0, 6.0, 6.0, 8.0, 8.0])
        measurements = references * 1.05 + np.array(
            [0.01, -0.01, 0.02, -0.02, 0.01, -0.01, 0.02, -0.02]
        )
        result = linearity(references, measurements)
        assert result.linearity(process_variation=12.0) == pytest.approx(abs(result.slope) * 12.0)

    def test_two_reference_levels_are_refused(self) -> None:
        """Two points define a line exactly, leaving nothing to test the slope."""
        with pytest.raises(InsufficientDataError, match="define a line exactly"):
            linearity(
                np.array([2.0, 2.0, 4.0, 4.0]),
                np.array([2.1, 2.0, 4.2, 4.1]),
            )

    def test_mismatched_arrays_are_refused(self) -> None:
        """Every measurement needs the reference it was taken against."""
        with pytest.raises(InsufficientDataError):
            linearity(np.array([2.0, 4.0, 6.0]), np.array([2.1, 4.2]))

    def test_an_exactly_constant_bias_is_refused(self) -> None:
        """A perfect fit has no residual variance, so the slope has no standard error."""
        references = np.array([2.0, 4.0, 6.0, 8.0])
        with pytest.raises(DegenerateSeriesError):
            linearity(references, references + 0.5)


class TestStability:
    """A control chart on a check standard, and what a signal on it means."""

    def test_a_stable_gauge_gives_limits_around_the_standard(self) -> None:
        """The centre line sits at what the gauge has been reading."""
        rng = np.random.default_rng(20260803)
        measurements = rng.normal(10.0, 0.05, 40)
        result = stability(measurements, WINDOW, reference_value=10.0)

        assert result.study.location.centre_line == pytest.approx(10.0, abs=0.05)
        assert result.n_measurements == 40

    def test_the_drift_from_the_standard_is_reported(self) -> None:
        """A gauge that has been reading high since it was installed shows here."""
        rng = np.random.default_rng(20260803)
        result = stability(rng.normal(10.3, 0.05, 40), WINDOW, reference_value=10.0)
        assert result.drift is not None
        assert result.drift == pytest.approx(0.3, abs=0.05)

    def test_drift_is_absent_without_a_standard(self) -> None:
        """Stability is detectable without a reference value; bias is not."""
        rng = np.random.default_rng(20260803)
        result = stability(rng.normal(10.0, 0.05, 40), WINDOW)
        assert result.drift is None
        assert result.reference_value is None

    def test_a_drifting_gauge_leaves_the_limits(self) -> None:
        """The chart is what catches a slow drift that a repeated t-test misses.

        A t-test against the reference, run monthly, keeps answering "no
        difference" through a drift of this size. The chart's own limits catch
        it because they describe what this gauge used to do.
        """
        rng = np.random.default_rng(20260803)
        drifting = rng.normal(10.0, 0.05, 40) + np.linspace(0.0, 0.6, 40)
        result = stability(drifting, WINDOW, reference_value=10.0)

        location = result.study.location
        beyond = np.abs(drifting - location.centre_line) > (location.ucl - location.centre_line)
        assert beyond.any(), "a drift of twelve sigma must reach the limits"

    def test_a_reversed_window_is_refused(self) -> None:
        """A window that ends before it starts describes no period."""
        rng = np.random.default_rng(20260803)
        with pytest.raises(ConfigurationError):
            stability(rng.normal(10.0, 0.05, 20), (WINDOW[1], WINDOW[0]))

    def test_a_flat_gauge_is_refused(self) -> None:
        """Identical readings give zero-width limits, so everything is a signal."""
        with pytest.raises(DegenerateSeriesError):
            stability(np.full(20, 10.0), WINDOW)
