"""Detection rate against injected shifts of known magnitude (TESTING_STRATEGY §3.5).

Each trial builds an individuals series from a normal process, estimates
Phase I limits on the pre-onset window, charts the full series against those
fixed limits, and scores Western Electric rules against the known onset. The
acceptance thresholds - >= 95% at 1.5sigma, >= 99% at 3sigma, localisation >= 80% within
+/-3 - are the claims the platform makes about itself.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import cache

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
from spc_platform.analytics.scoring import DetectionEvent, FaultOnset, score_detections
from spc_platform.analytics.scoring.metrics import DetectionScorecard, FaultScore
from spc_platform.domain.enums import ChartStatistic, ChartType, SigmaEstimator
from spc_platform.domain.ids import BaselineId, ParameterId, UnitSymbol

from .conftest import rule_set_of

pytestmark = pytest.mark.statistical

SEED = 20260805
TRIALS = 200
"""Independent charts. Binomial standard error ≈ 1.5% at a 95% rate."""

PRE_ONSET = 50
"""Phase I window. Long enough for a stable moving-range estimate."""

POST_ONSET = 40
"""Points watched after the shift. Above the Shewhart ARL1 at 1.5sigma."""

ONSET_INDEX = PRE_ONSET
SERIES_LENGTH = PRE_ONSET + POST_ONSET

DETECTION_RATE_AT_1_5 = 0.95
DETECTION_RATE_AT_3_0 = 0.99
LOCALISATION_RATE = 0.80

EPOCH = datetime(2026, 1, 1, tzinfo=UTC)
PARAMETER = ParameterId("SHIFT_STUDY")
BASELINE = BaselineId("BL-POWER")
UNIT = UnitSymbol("1")


def _detections_for(values: np.ndarray) -> tuple[DetectionEvent, ...]:
    """Phase I on the pre-onset window, then Western Electric on the full series."""
    study = individuals_study(values[:ONSET_INDEX])
    timestamps = tuple(EPOCH + timedelta(hours=index) for index in range(values.size))
    panel = individuals_chart(
        PlottedPoints(
            values=np.asarray(values, dtype=np.float64),
            timestamps=timestamps,
            subgroup_sizes=(1,),
        ),
        PanelIdentity(
            parameter_id=PARAMETER,
            baseline_id=BASELINE,
            chart_type=ChartType.I_MR,
            statistic=ChartStatistic.INDIVIDUAL,
            unit=UNIT,
        ),
        FixedIndividualsLimits(
            centre_line=study.location.centre_line,
            sigma_within=study.sigma_within.value,
            sigma_estimator=SigmaEstimator.MR_BAR_D2,
        ),
    )
    violations = evaluate.evaluate_panel(
        rule_set_of(*catalogue.WESTERN_ELECTRIC, name="western-electric"),
        panel,
    )
    return tuple(
        DetectionEvent(point_index=violation.point_index, detector="western_electric")
        for violation in violations
    )


def _scorecard_for(shift_sigma: float) -> DetectionScorecard:
    """One fault per trial, aggregated into a single scorecard."""
    fault_scores: list[FaultScore] = []
    false_alarms = 0
    for trial in range(TRIALS):
        rng = np.random.default_rng(SEED + trial)
        values = rng.normal(0.0, 1.0, size=SERIES_LENGTH)
        values[ONSET_INDEX:] += shift_sigma
        events = _detections_for(values)
        false_alarms += sum(1 for event in events if event.point_index < ONSET_INDEX)
        card = score_detections(
            events,
            (
                FaultOnset(
                    fault_id=f"shift-{shift_sigma:g}-{trial}",
                    onset_index=ONSET_INDEX,
                    magnitude_sigma=shift_sigma,
                    kind="step_shift",
                ),
            ),
            series_length=SERIES_LENGTH,
        )
        fault_scores.extend(card.faults)
    return DetectionScorecard(
        faults=tuple(fault_scores),
        series_length=SERIES_LENGTH * TRIALS,
        false_alarms=false_alarms,
    )


@cache
def card_at_1_5() -> DetectionScorecard:
    """Return the 1.5-sigma study, computed once for every assertion that reads it."""
    return _scorecard_for(1.5)


@cache
def card_at_3_0() -> DetectionScorecard:
    """Return the 3-sigma study, computed once for every assertion that reads it."""
    return _scorecard_for(3.0)


class TestDetectionRateAgainstKnownShifts:
    """The acceptance thresholds from TESTING_STRATEGY.md §3.5."""

    def test_detection_rate_at_one_and_a_half_sigma(self) -> None:
        """>= 95% of 1.5sigma step shifts are detected within the watch window."""
        card = card_at_1_5()
        assert card.detection_rate >= DETECTION_RATE_AT_1_5, (
            f"detection rate {card.detection_rate:.3f} below {DETECTION_RATE_AT_1_5} "
            f"on {card.faults_scored} trials"
        )

    def test_detection_rate_at_three_sigma(self) -> None:
        """>= 99% of 3sigma step shifts are detected - usually on the onset point."""
        card = card_at_3_0()
        assert card.detection_rate >= DETECTION_RATE_AT_3_0, (
            f"detection rate {card.detection_rate:.3f} below {DETECTION_RATE_AT_3_0}"
        )

    def test_localisation_within_three_points_at_three_sigma(self) -> None:
        """>= 80% of 3sigma detections land within +/-3 of onset.

        At 1.5sigma a Shewhart chart's ARL1 is about fifteen points, so most
        detections fall outside a +/-3 window by construction; that is a fact
        about the chart, not a scoring defect. The localisation claim is
        therefore asserted where it is achievable - on a shift the chart is
        designed to catch on contact.
        """
        card = card_at_3_0()
        assert card.localisation_rate >= LOCALISATION_RATE, (
            f"localisation rate {card.localisation_rate:.3f} below {LOCALISATION_RATE}"
        )

    def test_false_alarms_on_the_pre_onset_window_are_plausible(self) -> None:
        """Pre-onset signals sit near the Western Electric false-alarm rate.

        Combined WE ARL₀ ≈ 91.75, so about PRE_ONSET/91.75 signals are expected
        per trial on the clean window. Estimated Phase I limits inflate that
        relative to known-sigma theory; the band below absorbs the inflation.
        Precise ARL₀ is asserted in ``test_arl.py``.
        """
        card = card_at_1_5()
        expected = TRIALS * PRE_ONSET / 91.75
        assert expected * 0.5 <= card.false_alarms <= expected * 2.5, (
            f"false alarms {card.false_alarms} outside [{expected * 0.5:.0f}, {expected * 2.5:.0f}]"
        )
