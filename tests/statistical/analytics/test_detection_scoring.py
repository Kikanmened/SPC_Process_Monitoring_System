"""The scoring harness itself, verified on cases whose answers are countable.

TESTING_STRATEGY.md §3.5 requires that the scorecard be checked on a
constructed case where detection rate, latency, and localisation are known by
hand - so a wrong scorecard cannot flatter a wrong engine.
"""

from __future__ import annotations

import pytest

from spc_platform.analytics.scoring import (
    DetectionEvent,
    FaultOnset,
    ScoringPolicy,
    score_detections,
)
from spc_platform.common.errors import GroundTruthError

pytestmark = pytest.mark.statistical

SERIES_LENGTH = 100


def _fault(fault_id: str, onset: int, magnitude: float = 1.5) -> FaultOnset:
    """One fault onset in the series."""
    return FaultOnset(
        fault_id=fault_id,
        onset_index=onset,
        magnitude_sigma=magnitude,
        kind="step_shift",
    )


class TestHandCountedScorecard:
    """Three faults, detections placed where the arithmetic is obvious."""

    def test_perfect_detection_scores_one(self) -> None:
        """Each fault has a detection at its onset: rate 1, latency 0, localised."""
        truth = (_fault("A", 20), _fault("B", 50), _fault("C", 80))
        detections = (
            DetectionEvent(20),
            DetectionEvent(50),
            DetectionEvent(80),
        )
        card = score_detections(detections, truth, series_length=SERIES_LENGTH)
        assert card.detection_rate == 1.0
        assert card.localisation_rate == 1.0
        assert card.mean_latency == 0.0
        assert card.false_alarms == 0
        assert card.rate_at_or_above(1.5) == 1.0

    def test_a_miss_lowers_the_rate_by_one_third(self) -> None:
        """Two of three faults detected: rate 2/3."""
        truth = (_fault("A", 20), _fault("B", 50), _fault("C", 80))
        detections = (DetectionEvent(20), DetectionEvent(80))
        card = score_detections(detections, truth, series_length=SERIES_LENGTH)
        assert card.faults_detected == 2
        assert card.detection_rate == pytest.approx(2 / 3)
        assert card.faults[1].detected is False

    def test_latency_and_localisation_are_counted_from_onset(self) -> None:
        """Detection three points after onset is localised; five points is not."""
        truth = (_fault("near", 20), _fault("far", 50))
        detections = (DetectionEvent(23), DetectionEvent(55))
        card = score_detections(detections, truth, series_length=SERIES_LENGTH)
        assert card.faults[0].latency == 3
        assert card.faults[0].localised is True
        assert card.faults[1].latency == 5
        assert card.faults[1].localised is False
        assert card.localisation_rate == pytest.approx(0.5)
        assert card.mean_latency == pytest.approx(4.0)

    def test_signals_before_the_first_onset_are_false_alarms(self) -> None:
        """Two early signals on a clean prefix of 20 points: rate 2/20."""
        truth = (_fault("A", 20),)
        detections = (
            DetectionEvent(5),
            DetectionEvent(12),
            DetectionEvent(22),  # the real detection
        )
        card = score_detections(detections, truth, series_length=SERIES_LENGTH)
        assert card.false_alarms == 2
        assert card.false_alarm_rate == pytest.approx(2 / 20)
        assert card.detection_rate == 1.0

    def test_repeated_signals_after_onset_are_not_false_alarms(self) -> None:
        """A rule that keeps firing after the fault is evidence, not wolf-crying."""
        truth = (_fault("A", 20),)
        detections = tuple(DetectionEvent(index) for index in range(20, 30))
        card = score_detections(detections, truth, series_length=SERIES_LENGTH)
        assert card.false_alarms == 0
        assert card.faults[0].detection_index == 20

    def test_max_latency_caps_what_counts_as_detection(self) -> None:
        """A detection past the latency cap is a miss, not a late hit."""
        truth = (_fault("A", 20),)
        detections = (DetectionEvent(30),)
        card = score_detections(
            detections,
            truth,
            series_length=SERIES_LENGTH,
            policy=ScoringPolicy(max_latency=5),
        )
        assert card.detection_rate == 0.0

    def test_rate_at_or_above_filters_by_magnitude(self) -> None:
        """The 1.5sigma claim ignores the small fault that was missed."""
        truth = (
            _fault("small", 20, magnitude=1.0),
            _fault("large", 50, magnitude=2.0),
        )
        detections = (DetectionEvent(50),)
        card = score_detections(detections, truth, series_length=SERIES_LENGTH)
        assert card.detection_rate == pytest.approx(0.5)
        assert card.rate_at_or_above(1.5) == 1.0


class TestRefusals:
    """Indices outside the series are a ground-truth mismatch, not a quiet skip."""

    def test_an_onset_past_the_series_is_refused(self) -> None:
        """Onset at 100 in a series of length 100 is out of range."""
        with pytest.raises(GroundTruthError, match="onset falls outside"):
            score_detections(
                (),
                (_fault("A", 100),),
                series_length=SERIES_LENGTH,
            )

    def test_a_detection_past_the_series_is_refused(self) -> None:
        """A detection index that cannot address the series is refused."""
        with pytest.raises(GroundTruthError, match="detection falls outside"):
            score_detections(
                (DetectionEvent(100),),
                (_fault("A", 20),),
                series_length=SERIES_LENGTH,
            )
