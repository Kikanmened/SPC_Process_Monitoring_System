"""Score detections against known fault onsets (TESTING_STRATEGY.md §3.5).

The harness itself is verified on constructed cases where the rate, latency,
and localisation are known by hand — so a wrong scorecard cannot flatter a
wrong engine. Production activation of detectors, registries, and false-alarm
gates are proposed requirements (FR-AD01 - FR-AD04) and are not implemented
here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from spc_platform.analytics.scoring.ground_truth import FaultOnset
from spc_platform.common.errors import GroundTruthError

DEFAULT_LOCALISATION_TOLERANCE = 3
"""A detection within this many points of onset counts as localised.

TESTING_STRATEGY.md section 3.5: localisation of 80% or better within +/-3 of onset.
"""


@dataclass(frozen=True, slots=True)
class DetectionEvent:
    """One signal raised against the series under score.

    Attributes
    ----------
    point_index
        Index in the same series the fault onsets refer to.
    detector
        Free-text identity of the source, for the scorecard report. The scorer
        does not interpret it.
    """

    point_index: int
    detector: str = "rule_set"

    def __post_init__(self) -> None:
        """Reject a detection that cannot sit in any series."""
        if self.point_index < 0:
            raise ValueError(f"detection point_index must be non-negative, got {self.point_index}")


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    """How generously a detection may miss the onset and still count.

    Attributes
    ----------
    localisation_tolerance
        Absolute point distance from onset that still counts as localised.
    max_latency
        Latest point index after onset at which a detection still counts. None
        means any detection at or after onset counts, however late.
    """

    localisation_tolerance: int = DEFAULT_LOCALISATION_TOLERANCE
    max_latency: int | None = None


@dataclass(frozen=True, slots=True)
class FaultScore:
    """How one fault fared against the detections."""

    fault_id: str
    kind: str
    magnitude_sigma: float
    onset_index: int
    detected: bool
    detection_index: int | None
    latency: int | None
    localised: bool


@dataclass(frozen=True, slots=True)
class DetectionScorecard:
    """Aggregate detection performance against a set of known faults.

    Attributes
    ----------
    faults
        Per-fault outcomes, in the order supplied.
    series_length
        Points in the scored series — the denominator for the false-alarm rate.
    false_alarms
        Detections that fell before every fault's onset, or between faults in
        regions the policy treats as clean. Counted as detections whose point
        index is not credited to any fault.
    """

    faults: tuple[FaultScore, ...]
    series_length: int
    false_alarms: int

    @property
    def faults_scored(self) -> int:
        """Number of faults the scorecard covers."""
        return len(self.faults)

    @property
    def faults_detected(self) -> int:
        """Faults with at least one credited detection."""
        return sum(1 for fault in self.faults if fault.detected)

    @property
    def detection_rate(self) -> float:
        """Fraction of faults detected. Zero when no faults were scored."""
        if not self.faults:
            return 0.0
        return self.faults_detected / self.faults_scored

    @property
    def localisation_rate(self) -> float:
        """Fraction of *detected* faults localised within tolerance."""
        detected = [fault for fault in self.faults if fault.detected]
        if not detected:
            return 0.0
        return sum(1 for fault in detected if fault.localised) / len(detected)

    @property
    def mean_latency(self) -> float | None:
        """Mean points from onset to first credited detection, or None if none."""
        latencies = [fault.latency for fault in self.faults if fault.latency is not None]
        if not latencies:
            return None
        return sum(latencies) / len(latencies)

    @property
    def false_alarm_rate(self) -> float:
        """False alarms per point on the clean portion of the series.

        The clean portion is every point that is not at or after any fault
        onset. A series that is entirely post-onset has no clean points and
        reports a rate of zero rather than dividing by zero — there was no
        opportunity for a false alarm.
        """
        clean = self._clean_points()
        if clean == 0:
            return 0.0
        return self.false_alarms / clean

    def rate_at_or_above(self, magnitude_sigma: float) -> float:
        """Return the detection rate among faults of at least ``magnitude_sigma``."""
        relevant = [fault for fault in self.faults if fault.magnitude_sigma >= magnitude_sigma]
        if not relevant:
            return 0.0
        return sum(1 for fault in relevant if fault.detected) / len(relevant)

    def _clean_points(self) -> int:
        """Points strictly before the earliest fault onset."""
        if not self.faults:
            return self.series_length
        earliest = min(fault.onset_index for fault in self.faults)
        return max(0, min(earliest, self.series_length))


def score_detections(
    detections: Sequence[DetectionEvent],
    truth: Sequence[FaultOnset],
    *,
    series_length: int,
    policy: ScoringPolicy | None = None,
) -> DetectionScorecard:
    """Compute detection rate, latency, localisation, and false-alarm rate.

    Each fault owns the window from its onset up to the next fault's onset.
    The earliest detection inside that window (also respecting ``max_latency``)
    is credited. Signals strictly before the earliest onset count as false
    alarms; repeated signals after onset do not.

    Parameters
    ----------
    detections
        Signals raised against the series, in any order.
    truth
        Injected faults with their onset indices in the same series.
    series_length
        Number of plotted points in the series. Must cover every onset and
        every detection index.
    policy
        Localisation tolerance and optional latency cap.

    Returns
    -------
    DetectionScorecard
        Aggregate and per-fault outcomes.

    Raises
    ------
    GroundTruthError
        If an onset or detection index falls outside the series, or the series
        length is not positive.
    """
    active = policy if policy is not None else ScoringPolicy()
    if series_length < 1:
        raise GroundTruthError(
            "a scorecard needs a series of at least one point",
            series_length=series_length,
        )
    _require_indices_in_series(detections, truth, series_length)

    remaining = sorted(detections, key=lambda event: event.point_index)
    ordered_truth = sorted(truth, key=lambda item: item.onset_index)
    fault_scores: list[FaultScore] = []

    for index, fault in enumerate(ordered_truth):
        # A fault owns the window from its onset up to (but not including) the
        # next fault's onset. Without that bound, a late detection of fault N+1
        # would be stolen by fault N and both rates would be wrong.
        window_end = (
            ordered_truth[index + 1].onset_index
            if index + 1 < len(ordered_truth)
            else series_length
        )
        match = _first_credit(remaining, fault, active, window_end)
        if match is None:
            fault_scores.append(
                FaultScore(
                    fault_id=fault.fault_id,
                    kind=fault.kind,
                    magnitude_sigma=fault.magnitude_sigma,
                    onset_index=fault.onset_index,
                    detected=False,
                    detection_index=None,
                    latency=None,
                    localised=False,
                )
            )
            continue
        latency = match.point_index - fault.onset_index
        fault_scores.append(
            FaultScore(
                fault_id=fault.fault_id,
                kind=fault.kind,
                magnitude_sigma=fault.magnitude_sigma,
                onset_index=fault.onset_index,
                detected=True,
                detection_index=match.point_index,
                latency=latency,
                localised=latency <= active.localisation_tolerance,
            )
        )

    # Only signals on the clean prefix are false alarms. Repeated signals after
    # onset are the fault's continuing evidence, not cries of wolf.
    earliest = min((fault.onset_index for fault in truth), default=series_length)
    false_alarms = sum(1 for event in remaining if event.point_index < earliest)

    # Preserve the caller's fault order in the scorecard.
    by_id = {score.fault_id: score for score in fault_scores}
    ordered = tuple(by_id[fault.fault_id] for fault in truth)
    return DetectionScorecard(
        faults=ordered,
        series_length=series_length,
        false_alarms=false_alarms,
    )


def _first_credit(
    detections: Sequence[DetectionEvent],
    fault: FaultOnset,
    policy: ScoringPolicy,
    window_end: int,
) -> DetectionEvent | None:
    """Earliest detection inside ``fault``'s window, or None."""
    latest = window_end - 1
    if policy.max_latency is not None:
        latest = min(latest, fault.onset_index + policy.max_latency)
    for event in detections:
        if event.point_index < fault.onset_index:
            continue
        if event.point_index > latest:
            return None
        return event
    return None


def _require_indices_in_series(
    detections: Sequence[DetectionEvent],
    truth: Sequence[FaultOnset],
    series_length: int,
) -> None:
    """Refuse a scorecard whose indices cannot refer to the series."""
    for fault in truth:
        if fault.onset_index >= series_length:
            raise GroundTruthError(
                "fault onset falls outside the scored series",
                fault_id=fault.fault_id,
                onset_index=fault.onset_index,
                series_length=series_length,
            )
    for event in detections:
        if event.point_index >= series_length:
            raise GroundTruthError(
                "detection falls outside the scored series",
                point_index=event.point_index,
                series_length=series_length,
            )
