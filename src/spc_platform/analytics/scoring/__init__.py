"""Detection performance scoring against known ground truth (Module 6).

A test-tier and validation harness. Detector registries, activation gates, and
false-alarm characterisation-before-activation are proposed requirements
(FR-AD01 - FR-AD04) and are not implemented here.
"""

from spc_platform.analytics.scoring.ground_truth import FaultOnset
from spc_platform.analytics.scoring.metrics import (
    DEFAULT_LOCALISATION_TOLERANCE,
    DetectionEvent,
    DetectionScorecard,
    FaultScore,
    ScoringPolicy,
    score_detections,
)

__all__ = [
    "DEFAULT_LOCALISATION_TOLERANCE",
    "DetectionEvent",
    "DetectionScorecard",
    "FaultOnset",
    "FaultScore",
    "ScoringPolicy",
    "score_detections",
]
