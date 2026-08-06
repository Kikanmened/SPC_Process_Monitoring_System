"""In-memory adapters for Phase 11 support ports."""

from __future__ import annotations

from datetime import datetime

from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.ports.violation_repository import StoredViolation
from spc_platform.common.errors import UnauthorisedActionError
from spc_platform.domain.disposition import Disposition
from spc_platform.domain.ids import ActorId, LotId, ParameterId, ProductId
from spc_platform.domain.specification_limit import SpecificationLimit


class FakeAuthorisation:
    """Permit all actions except those listed in ``denied``."""

    def __init__(self, denied: frozenset[tuple[str, ProtectedAction]] | None = None) -> None:
        self._denied = denied or frozenset()

    def require(self, actor: ActorId, action: ProtectedAction) -> None:
        """Raise when ``(actor, action)`` is in the deny set."""
        if (str(actor), action) in self._denied:
            raise UnauthorisedActionError(
                "actor is not permitted to perform this action",
                actor=str(actor),
                action=action.value,
            )


class AllowAllAuthorisation:
    """Permissive authorisation for local composition roots."""

    def require(self, actor: ActorId, action: ProtectedAction) -> None:
        """Permit every action without checking roles."""
        _ = (actor, action)


class FakeViolationRepository:
    """Dict-backed violation store."""

    def __init__(self) -> None:
        self._items: dict[str, StoredViolation] = {}

    def save(self, stored: StoredViolation) -> None:
        """Insert or replace."""
        self._items[stored.violation_id] = stored

    def get(self, violation_id: str) -> StoredViolation | None:
        """Return by id."""
        return self._items.get(violation_id)

    def list_open(self, parameter_id: ParameterId | None = None) -> tuple[StoredViolation, ...]:
        """Unacknowledged violations, newest first by timestamp."""
        open_items = [
            item
            for item in self._items.values()
            if not item.acknowledged
            and (parameter_id is None or item.violation.parameter_id == parameter_id)
        ]
        open_items.sort(key=lambda item: item.violation.timestamp, reverse=True)
        return tuple(open_items)

    def acknowledge(
        self,
        violation_id: str,
        *,
        actor: ActorId,
        timestamp: datetime,
    ) -> StoredViolation:
        """Mark acknowledged."""
        current = self._items.get(violation_id)
        if current is None:
            message = f"unknown violation: {violation_id}"
            raise KeyError(message)
        updated = current.model_copy(
            update={
                "acknowledged": True,
                "acknowledged_by": actor,
                "acknowledged_at": timestamp,
            }
        )
        self._items[violation_id] = updated
        return updated


class FakeDispositionRepository:
    """List-backed disposition store."""

    def __init__(self) -> None:
        self._items: list[Disposition] = []

    def append(self, disposition: Disposition) -> None:
        """Append one disposition."""
        self._items.append(disposition)

    def list_for(self, lot_id: LotId) -> tuple[Disposition, ...]:
        """Dispositions for the lot."""
        return tuple(item for item in self._items if item.lot_id == lot_id)


class FakeSpecificationRepository:
    """In-memory specification store."""

    def __init__(self) -> None:
        self._items: list[SpecificationLimit] = []

    def save(self, specification: SpecificationLimit) -> None:
        """Store a specification."""
        self._items.append(specification)

    def effective_for(
        self,
        parameter_id: ParameterId,
        product_id: ProductId,
        *,
        at: datetime,
    ) -> SpecificationLimit | None:
        """Return the latest specification in force at ``at``."""
        candidates = [
            item
            for item in self._items
            if item.parameter_id == parameter_id
            and item.product_id == product_id
            and item.effective_from <= at
            and (item.effective_to is None or item.effective_to > at)
        ]
        if not candidates:
            return None
        candidates.sort(key=lambda item: item.effective_from, reverse=True)
        return candidates[0]
