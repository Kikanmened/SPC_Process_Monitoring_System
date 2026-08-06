"""Ground-truth fault onsets the scorecard is measured against.

These types are deliberately not the generator's ``FaultRecord``. The scoring
harness lives in ``analytics/`` and cannot import ``simulation/`` (ADR-0021);
the test tier bridges the two by projecting a manifest onto the records here.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FaultOnset:
    """One injected fault, located in the series under score.

    Attributes
    ----------
    fault_id
        Stable identity, carried into the scorecard so a miss names what missed.
    onset_index
        Index of the first plotted point affected by the fault, in the series
        the detections were raised against. Zero-based.
    magnitude_sigma
        Fault size in units of the process sigma the chart uses. The acceptance
        thresholds in TESTING_STRATEGY.md §3.5 are stated in these units.
    kind
        Free-text kind label for reporting. Not an enum: the scorer does not
        branch on kind, and binding it to the generator's vocabulary would pull
        simulation concepts into analytics.
    """

    fault_id: str
    onset_index: int
    magnitude_sigma: float
    kind: str = ""

    def __post_init__(self) -> None:
        """Reject an onset that cannot sit in any series."""
        if self.onset_index < 0:
            raise ValueError(
                f"fault {self.fault_id!r} onset_index must be non-negative, got {self.onset_index}"
            )
        if not self.fault_id:
            raise ValueError("fault_id must be non-empty")
