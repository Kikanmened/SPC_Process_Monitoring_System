"""Material hierarchy: lot, wafer, site.

A wafer belongs to exactly one lot; slot ∈ 1..25 (SYSTEM_ARCHITECTURE.md §3.1).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from spc_platform.domain.errors import DomainInvariantError
from spc_platform.domain.ids import LotId, SiteId, WaferId

_SLOT_MIN = 1
_SLOT_MAX = 25
_WAFER_RADIUS_MM = 150.0


class Lot(BaseModel):
    """The unit of material movement through the fab."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lot_id: LotId
    product_id: str


class Wafer(BaseModel):
    """A single substrate, identified by lot and slot."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    wafer_id: WaferId
    lot_id: LotId
    slot: int = Field(ge=_SLOT_MIN, le=_SLOT_MAX)

    @model_validator(mode="after")
    def _wafer_id_matches_lot_and_slot(self) -> Wafer:
        expected = f"{self.lot_id}:{self.slot}"
        if str(self.wafer_id) != expected:
            raise DomainInvariantError(
                "wafer_id must be '{lot_id}:{slot}'",
                wafer_id=str(self.wafer_id),
                expected=expected,
            )
        return self


class Site(BaseModel):
    """A measurement location at true coordinates from wafer centre (mm)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    site_id: SiteId
    site_x_mm: float
    site_y_mm: float

    @field_validator("site_id")
    @classmethod
    def _positive_site(cls, value: SiteId) -> SiteId:
        if int(value) < 1:
            raise DomainInvariantError("site_id must be >= 1", site_id=int(value))
        return value

    @model_validator(mode="after")
    def _within_wafer(self) -> Site:
        radius_sq = self.site_x_mm**2 + self.site_y_mm**2
        if radius_sq > _WAFER_RADIUS_MM**2:
            raise DomainInvariantError(
                "site coordinates lie outside the 300 mm wafer",
                site_x_mm=self.site_x_mm,
                site_y_mm=self.site_y_mm,
            )
        return self
