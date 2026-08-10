"""OCAP linkage from the control plan (FR-A04)."""

from __future__ import annotations

from typing import Protocol

from spc_platform.domain.ids import OcapId, ParameterId, ProductId


class ControlPlanLookup(Protocol):
    """Resolve the OCAP defined for a characteristic."""

    def ocap_for(
        self,
        parameter_id: ParameterId,
        product_id: ProductId | None = None,
    ) -> OcapId | None:
        """Return the OCAP id, or ``None`` when the plan has no matching row."""
        ...
