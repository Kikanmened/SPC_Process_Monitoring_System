"""Load effective specification limits for capability (Module 4)."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from spc_platform.domain.ids import ParameterId, ProductId
from spc_platform.domain.specification_limit import SpecificationLimit


class SpecificationRepository(Protocol):
    """Read approved specification limits."""

    def effective_for(
        self,
        parameter_id: ParameterId,
        product_id: ProductId,
        *,
        at: datetime,
    ) -> SpecificationLimit | None:
        """Return the specification in force at ``at``, or None."""
        ...

    def save(self, specification: SpecificationLimit) -> None:
        """Store a specification (tests and composition roots)."""
        ...
