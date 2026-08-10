"""Persistence for excursion lifecycle records."""

from __future__ import annotations

from typing import Protocol

from spc_platform.domain.excursion import Excursion
from spc_platform.domain.ids import ExcursionId, ParameterId


class ExcursionRepository(Protocol):
    """Store and load excursions."""

    def save(self, excursion: Excursion) -> None:
        """Insert or replace an excursion."""
        ...

    def get(self, excursion_id: ExcursionId) -> Excursion | None:
        """Return by id, or ``None`` when unknown."""
        ...

    def list_open(self, parameter_id: ParameterId | None = None) -> tuple[Excursion, ...]:
        """Excursions that are not closed, newest first."""
        ...
