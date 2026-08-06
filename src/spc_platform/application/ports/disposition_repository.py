"""Append disposition records (FR-A03)."""

from __future__ import annotations

from typing import Protocol

from spc_platform.domain.disposition import Disposition
from spc_platform.domain.ids import LotId


class DispositionRepository(Protocol):
    """Append-only disposition store."""

    def append(self, disposition: Disposition) -> None:
        """Record one disposition."""
        ...

    def list_for(self, lot_id: LotId) -> tuple[Disposition, ...]:
        """Return dispositions for the lot in append order."""
        ...
