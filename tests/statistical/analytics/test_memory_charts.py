"""EWMA and CUSUM against Montgomery's worked examples, and their invariants.

Both examples use the same 30 observations, which is the point of them: the two
charts are alternative answers to the same question, and Montgomery runs them
over one data set so the comparison is like for like. Both are tuned to detect a
one sigma shift, and the process does shift by one sigma partway through. Both
signal at observation 29.

References
----------
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., Table 9.1 (the data), Example 9.1 (CUSUM), Example 9.2 (EWMA).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spc_platform.analytics.charts.memory import (
    CusumDesign,
    EwmaDesign,
    MemoryChartSettings,
    cusum_chart,
    ewma,
    ewma_chart,
)
from spc_platform.analytics.charts.panels import PanelIdentity, PlottedPoints
from spc_platform.common.errors import ConfigurationError, InsufficientDataError
from spc_platform.common.types import FloatArray
from spc_platform.domain.charting import ChartPanel, ControlChart
from spc_platform.domain.enums import ChartStatistic, ChartType, SigmaEstimator
from spc_platform.domain.ids import BaselineId, ParameterId, UnitSymbol

MOLECULAR_WEIGHT = (
    9.45, 7.99, 9.29, 11.66, 12.16, 10.18, 8.04, 11.46, 9.20, 10.34,
    9.03, 11.47, 10.51, 9.40, 10.08, 9.37, 10.62, 10.31, 8.52, 10.84,
    10.90, 9.33, 12.29, 11.50, 10.60, 11.08, 10.38, 11.62, 11.31, 10.52,
)  # fmt: skip
"""Montgomery Table 9.1: 30 observations with target 10 and sigma 1.

The process mean shifts up by one sigma at observation 21, which neither chart
is told about and both are expected to find.
"""

TARGET = 10.0
PROCESS_SIGMA = 1.0

PUBLISHED_FIRST_SIGNAL = 29
"""Both examples report the first out-of-control point at observation 29.

One-based, as Montgomery numbers them.
"""


def observations(values: tuple[float, ...] = MOLECULAR_WEIGHT) -> PlottedPoints:
    """Wrap a series as individually measured points one hour apart."""
    start = datetime(2026, 1, 1, tzinfo=UTC)
    return PlottedPoints(
        values=np.array(values, dtype=np.float64),
        timestamps=tuple(start + timedelta(hours=i) for i in range(len(values))),
        subgroup_sizes=(1,) * len(values),
    )


def identity(statistic: ChartStatistic, chart_type: ChartType) -> PanelIdentity:
    """Name the parameter and baseline a memory chart is drawn for."""
    return PanelIdentity(
        parameter_id=ParameterId("molecular_weight"),
        baseline_id=BaselineId("baseline-1"),
        chart_type=chart_type,
        statistic=statistic,
        unit=UnitSymbol("g/mol"),
    )


def baseline(sigma: float = PROCESS_SIGMA, target: float = TARGET) -> MemoryChartSettings:
    """Build settings for a qualified baseline with a known target and sigma."""
    return MemoryChartSettings(
        target=target,
        sigma=sigma,
        sigma_estimator=SigmaEstimator.MR_BAR_D2,
    )


def signals_above(panel: ChartPanel) -> list[int]:
    """One-based positions where a plotted point sits above its upper limit."""
    assert panel.limits.ucl is not None
    values = np.asarray(panel.series.values)
    upper = np.asarray(panel.limits.ucl)
    return [int(position) + 1 for position in np.flatnonzero(values > upper)]


def signals_outside(panel: ChartPanel) -> list[int]:
    """One-based positions where a plotted point sits outside a limit that exists."""
    values = np.asarray(panel.series.values)
    outside = np.zeros(values.shape, dtype=bool)
    if panel.limits.ucl is not None:
        outside |= values > np.asarray(panel.limits.ucl)
    if panel.limits.lcl is not None:
        outside |= values < np.asarray(panel.limits.lcl)
    return [int(position) + 1 for position in np.flatnonzero(outside)]


class TestTheMontgomeryCusum:
    """Example 9.1: tabular CUSUM with k = 0.5 and h = 5."""

    @pytest.fixture
    def chart(self) -> ControlChart:
        """Run the published scheme over the published data."""
        return cusum_chart(
            observations(),
            identity(ChartStatistic.CUSUM_UPPER, ChartType.CUSUM),
            baseline(),
            CusumDesign(slack=0.5, decision=5.0),
        )

    def test_the_upper_arm_reaches_the_published_value(self, chart: ControlChart) -> None:
        """C+ at observation 29 is 5.28, having crossed h = 5 for the first time."""
        upper = chart.location.series.values
        assert upper[28] == pytest.approx(5.28, abs=5e-3)

    def test_the_scheme_signals_where_montgomery_says(self, chart: ControlChart) -> None:
        """The first signal is at observation 29, on the upper arm."""
        assert signals_above(chart.location)[0] == PUBLISHED_FIRST_SIGNAL

    def test_the_lower_arm_never_signals(self, chart: ControlChart) -> None:
        """The shift is upward, so the arm looking for a decrease stays quiet."""
        assert chart.dispersion is not None
        assert signals_above(chart.dispersion) == []

    def test_the_arms_accumulate_only_after_the_shift(self, chart: ControlChart) -> None:
        """C+ is at zero for observation 3 and climbing steadily by observation 28.

        The in-control stretch resets the sum repeatedly, which is what keeps a
        CUSUM from wandering; the run from 23 onward is the shift being found.
        """
        upper = chart.location.series.values
        assert upper[2] == pytest.approx(0.0)
        assert upper[27] == pytest.approx(4.47, abs=5e-3)

    def test_both_arms_are_non_negative(self, chart: ControlChart) -> None:
        """The reset at zero is what makes this a detector, not a random walk."""
        assert chart.dispersion is not None
        assert min(chart.location.series.values) >= 0.0
        assert min(chart.dispersion.series.values) >= 0.0

    def test_the_decision_interval_is_the_upper_limit(self, chart: ControlChart) -> None:
        """H = 5 in sigma units, and the arm is already in sigma units."""
        assert chart.location.limits.ucl is not None
        assert set(chart.location.limits.ucl) == {5.0}

    def test_the_arm_has_no_lower_limit_at_all(self, chart: ControlChart) -> None:
        """An arm that signals only from above has no lower side to signal on.

        Recording a lower limit of zero would be a different claim: it would
        make a CUSUM of exactly zero — the most in-control reading the statistic
        has — an out-of-control point.
        """
        assert chart.location.limits.lcl is None
        assert chart.dispersion is not None
        assert chart.dispersion.limits.lcl is None


class TestTheMontgomeryEwma:
    """Example 9.2: EWMA with lambda = 0.1 and L = 2.7 over the same data."""

    @pytest.fixture
    def panel(self) -> ChartPanel:
        """Run the published scheme over the published data."""
        return ewma_chart(
            observations(),
            identity(ChartStatistic.EWMA, ChartType.EWMA),
            baseline(),
            EwmaDesign(weight=0.1, sigma_multiplier=2.7),
        )

    def test_the_first_smoothed_point_is_the_published_one(self, panel: ChartPanel) -> None:
        """z1 = 0.1(9.45) + 0.9(10) = 9.945."""
        assert panel.series.values[0] == pytest.approx(9.945, abs=5e-4)

    def test_the_scheme_signals_where_montgomery_says(self, panel: ChartPanel) -> None:
        """The first signal is at observation 29, the same point the CUSUM finds."""
        assert signals_outside(panel)[0] == PUBLISHED_FIRST_SIGNAL

    def test_the_smoothed_value_at_the_signal(self, panel: ChartPanel) -> None:
        """z29 = 10.6468 against an upper limit of 10.6187."""
        assert panel.limits.ucl is not None
        assert panel.series.values[28] == pytest.approx(10.6468, abs=5e-4)
        assert panel.limits.ucl[28] == pytest.approx(10.6187, abs=5e-4)

    def test_the_limits_widen_towards_the_asymptote(self, panel: ChartPanel) -> None:
        """Exact limits start narrow and settle, which is why they are the default.

        Using the steady-state width from the first point would leave the early
        observations effectively unmonitored, since z has barely moved off the
        target and its variance is far below the asymptotic value.
        """
        upper = np.asarray(panel.limits.ucl)
        assert np.all(np.diff(upper) > 0.0)
        asymptote = TARGET + 2.7 * PROCESS_SIGMA * np.sqrt(0.1 / 1.9)
        assert upper[-1] == pytest.approx(asymptote, abs=1e-3)
        assert upper[0] < asymptote


class TestTheEwmaRecursion:
    """Properties of the smoother itself, independent of any chart."""

    def test_a_weight_of_one_reproduces_the_data(self) -> None:
        """At lambda = 1 the memory is empty and the chart is Shewhart's."""
        values = np.array(MOLECULAR_WEIGHT, dtype=np.float64)
        assert ewma(values, TARGET, 1.0) == pytest.approx(values)

    def test_a_constant_series_stays_at_its_own_level(self) -> None:
        """Starting on target, a process that never moves produces a flat line."""
        values = np.full(20, TARGET, dtype=np.float64)
        assert ewma(values, TARGET, 0.2) == pytest.approx(values)

    def test_the_smoother_converges_towards_a_step(self) -> None:
        """A sustained shift is approached geometrically and never overshot.

        This is the trade the chart makes: the lag is what suppresses the noise,
        and it is why an EWMA finds a small sustained shift that a Shewhart
        chart misses and is slower on a large sudden one.

        The approach is checked only while it is still resolvable in floating
        point. At lambda = 0.2 the remaining gap falls below the spacing of a
        double after roughly 160 steps, after which the series is exactly at the
        new level and the increments are legitimately zero.
        """
        shifted = TARGET + 5.0
        values = np.full(200, shifted, dtype=np.float64)
        smoothed = ewma(values, TARGET, 0.2)
        resolvable = smoothed < np.nextafter(shifted, -np.inf)
        assert np.all(np.diff(smoothed[resolvable]) > 0.0)
        assert np.all(smoothed <= shifted), "an EWMA never overshoots a step"
        assert smoothed[-1] == pytest.approx(shifted, abs=1e-12)

    @settings(max_examples=100, deadline=None)
    @given(
        weight=st.floats(min_value=0.05, max_value=1.0),
        offset=st.floats(min_value=-50.0, max_value=50.0),
        scale=st.floats(min_value=0.1, max_value=10.0),
    )
    def test_the_smoother_is_affine(self, weight: float, offset: float, scale: float) -> None:
        """Rescaling and shifting the input does the same to the output.

        The recursion is linear, so a chart in angstroms and the same chart in
        nanometres must signal at exactly the same points. If this failed, the
        chart would depend on the unit the fab happened to record.
        """
        values = np.array(MOLECULAR_WEIGHT, dtype=np.float64)
        plain = ewma(values, TARGET, weight)
        moved = ewma(scale * values + offset, scale * TARGET + offset, weight)
        assert moved == pytest.approx(scale * plain + offset, rel=1e-9, abs=1e-9)


class TestTheDetectionAdvantage:
    """The reason to accept the extra complexity over a Shewhart chart.

    Both schemes here are tuned for a one sigma shift, which a three sigma
    Shewhart chart takes an average of 44 observations to find.
    """

    SHEWHART_ARL_AT_ONE_SIGMA = 44.0
    """Montgomery §9.1: the ARL of a 3-sigma individuals chart to a 1-sigma shift."""

    def _shifted(self, seed: int, size: int = 400) -> FloatArray:
        """Draw an in-control process that shifts up by one sigma immediately."""
        rng = np.random.default_rng(seed)
        return rng.normal(TARGET + PROCESS_SIGMA, PROCESS_SIGMA, size)

    def test_the_cusum_finds_a_one_sigma_shift_far_sooner(self) -> None:
        """Averaged over 200 runs, well under the 44 a Shewhart chart needs."""
        runs = [
            signals_above(
                cusum_chart(
                    observations(tuple(self._shifted(seed))),
                    identity(ChartStatistic.CUSUM_UPPER, ChartType.CUSUM),
                    baseline(),
                ).location
            )
            for seed in range(200)
        ]
        first = [run[0] for run in runs if run]
        assert len(first) == len(runs), "every shifted run should signal"
        assert float(np.mean(first)) < self.SHEWHART_ARL_AT_ONE_SIGMA / 2.0

    def test_the_ewma_finds_a_one_sigma_shift_far_sooner(self) -> None:
        """The default design detects in about 10 observations, as published."""
        runs = [
            signals_outside(
                ewma_chart(
                    observations(tuple(self._shifted(seed))),
                    identity(ChartStatistic.EWMA, ChartType.EWMA),
                    baseline(),
                )
            )
            for seed in range(200)
        ]
        first = [run[0] for run in runs if run]
        assert len(first) == len(runs), "every shifted run should signal"
        assert float(np.mean(first)) < self.SHEWHART_ARL_AT_ONE_SIGMA / 2.0


class TestTheRefusals:
    """What these charts will not draw."""

    def test_a_single_observation_is_refused(self) -> None:
        """There is nothing to accumulate."""
        with pytest.raises(InsufficientDataError):
            ewma_chart(
                observations((10.0,)),
                identity(ChartStatistic.EWMA, ChartType.EWMA),
                baseline(),
            )

    def test_a_missing_timestamp_is_refused(self) -> None:
        """A memory chart is a statement about order, so the clock is not optional."""
        points = observations()
        broken = PlottedPoints(
            values=points.values,
            timestamps=points.timestamps[:-1],
            subgroup_sizes=points.subgroup_sizes,
        )
        with pytest.raises(InsufficientDataError):
            cusum_chart(
                broken,
                identity(ChartStatistic.CUSUM_UPPER, ChartType.CUSUM),
                baseline(),
            )

    @pytest.mark.parametrize("weight", [0.0, -0.1, 1.5])
    def test_a_weight_outside_the_unit_interval_is_refused(self, weight: float) -> None:
        """Zero never updates and above one oscillates with growing amplitude."""
        with pytest.raises(ConfigurationError):
            ewma_chart(
                observations(),
                identity(ChartStatistic.EWMA, ChartType.EWMA),
                baseline(),
                EwmaDesign(weight=weight),
            )

    def test_a_non_positive_sigma_is_refused(self) -> None:
        """Zero-width limits would signal on every point."""
        with pytest.raises(ConfigurationError):
            cusum_chart(
                observations(),
                identity(ChartStatistic.CUSUM_UPPER, ChartType.CUSUM),
                baseline(sigma=0.0),
            )

    @pytest.mark.parametrize(
        "design",
        [CusumDesign(slack=0.0), CusumDesign(decision=-1.0)],
    )
    def test_a_degenerate_cusum_design_is_refused(self, design: CusumDesign) -> None:
        """Without slack the sum never resets; without a threshold it never signals."""
        with pytest.raises(ConfigurationError):
            cusum_chart(
                observations(),
                identity(ChartStatistic.CUSUM_UPPER, ChartType.CUSUM),
                baseline(),
                design,
            )
