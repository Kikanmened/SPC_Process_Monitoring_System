"""Port for versioned, immutable baselines (FR-CF04, FR-AU04)."""

from __future__ import annotations

from typing import Protocol

from spc_platform.domain.baseline import Baseline
from spc_platform.domain.enums import BaselineStatus
from spc_platform.domain.ids import BaselineId, ParameterId


class BaselineStore(Protocol):
    """Persist baselines. Activation supersedes the previous active baseline."""

    def get(self, baseline_id: BaselineId) -> Baseline | None:
        """Return the baseline, or None if it has never been stored."""
        ...

    def active_for(self, parameter_id: ParameterId) -> Baseline | None:
        """Return the active baseline for the parameter, if any."""
        ...

    def save(self, baseline: Baseline) -> None:
        """Store a new baseline version.

        The baseline is immutable once saved. Saving an ``ACTIVE`` baseline
        marks any previously active baseline for the same parameter as
        ``SUPERSEDED`` and sets its successor relationship.
        """
        ...

    def list_for(
        self,
        parameter_id: ParameterId,
        *,
        status: BaselineStatus | None = None,
    ) -> tuple[Baseline, ...]:
        """Return baselines for the parameter, newest ``effective_from`` first."""
        ...
