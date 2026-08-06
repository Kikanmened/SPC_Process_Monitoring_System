"""Role-based authorisation decisions at the use-case boundary (NFR-SE04)."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from spc_platform.domain.ids import ActorId


class ProtectedAction(StrEnum):
    """Actions that require an explicit authorisation check."""

    ACKNOWLEDGE_VIOLATION = "acknowledge_violation"
    RECORD_DISPOSITION = "record_disposition"
    RECOMPUTE_BASELINE = "recompute_baseline"
    APPROVE_BASELINE = "approve_baseline"
    GENERATE_CAPABILITY_REPORT = "generate_capability_report"
    RUN_GAUGE_STUDY = "run_gauge_study"
    EVALUATE_LOT = "evaluate_lot"
    GET_WAFER_MAP = "get_wafer_map"


class Authorisation(Protocol):
    """Permit or refuse an actor for a named action."""

    def require(self, actor: ActorId, action: ProtectedAction) -> None:
        """Raise ``UnauthorisedActionError`` when the actor may not proceed."""
        ...
