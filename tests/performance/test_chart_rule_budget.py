"""Chart computation budget: 1 000 points with limits and the full rule set.

SYSTEM_ARCHITECTURE.md §7 and NFR-P01: < 50 ms. Absolute timing varies by
machine, so the test records a benchmark and fails only when a run exceeds the
budget by a clear margin — not on a single noisy sample.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from spc_platform.analytics.charts import (
    FixedIndividualsLimits,
    PanelIdentity,
    PlottedPoints,
    individuals_chart,
    individuals_study,
)
from spc_platform.analytics.rules import catalogue, evaluate
from spc_platform.domain.chart_spec import RuleDefinition, RuleSet
from spc_platform.domain.enums import (
    ChartStatistic,
    ChartType,
    SigmaEstimator,
    ViolationSeverity,
)
from spc_platform.domain.ids import BaselineId, ParameterId, UnitSymbol

pytestmark = pytest.mark.performance

POINTS = 1_000
BUDGET_SECONDS = 0.050
"""Fifty milliseconds for study + Phase II panel + Western Electric + Nelson."""

WARMUP = 3
SAMPLES = 11
SEED = 20260805
EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


def _run_once(values: np.ndarray) -> int:
    """One full evaluation; returns the number of violations found."""
    study = individuals_study(values[:200])
    timestamps = tuple(EPOCH + timedelta(minutes=index) for index in range(values.size))
    panel = individuals_chart(
        PlottedPoints(
            values=values,
            timestamps=timestamps,
            subgroup_sizes=(1,),
        ),
        PanelIdentity(
            parameter_id=ParameterId("PERF"),
            baseline_id=BaselineId("BL-PERF"),
            chart_type=ChartType.I_MR,
            statistic=ChartStatistic.INDIVIDUAL,
            unit=UnitSymbol("1"),
        ),
        FixedIndividualsLimits(
            centre_line=study.location.centre_line,
            sigma_within=study.sigma_within.value,
            sigma_estimator=SigmaEstimator.MR_BAR_D2,
        ),
    )
    rule_set = RuleSet(
        name="nelson",
        rules=tuple(
            RuleDefinition(rule_id=rule_id, severity=ViolationSeverity.WARNING)
            for rule_id in catalogue.NELSON
        ),
    )
    return len(evaluate.evaluate_panel(rule_set, panel))


def test_one_thousand_points_with_the_full_rule_set_stay_under_budget() -> None:
    """Median of several runs must sit under 50 ms (NFR-P01)."""
    rng = np.random.default_rng(SEED)
    values = np.asarray(rng.normal(0.0, 1.0, size=POINTS), dtype=np.float64)

    for _ in range(WARMUP):
        _run_once(values)

    durations: list[float] = []
    for _ in range(SAMPLES):
        started = time.perf_counter()
        _run_once(values)
        durations.append(time.perf_counter() - started)

    median = float(np.median(durations))
    assert median < BUDGET_SECONDS, (
        f"median {median * 1_000:.1f} ms exceeds the {BUDGET_SECONDS * 1_000:.0f} ms budget "
        f"(samples={[round(1_000 * d, 1) for d in durations]})"
    )
