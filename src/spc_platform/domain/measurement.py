"""One measured value at one site at one time.

Value + unit + timestamp + provenance — never a bare float
(SYSTEM_ARCHITECTURE.md §3.1, FR-D01).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from spc_platform.domain._time import require_aware
from spc_platform.domain.enums import MeasurementStatus
from spc_platform.domain.errors import DomainInvariantError
from spc_platform.domain.ids import (
    ChamberId,
    DataRevision,
    LotId,
    MeasurementId,
    MetrologyToolId,
    ParameterId,
    ProductId,
    RecipeId,
    SiteId,
    StepId,
    ToolId,
    UnitSymbol,
    WaferId,
)


class Measurement(BaseModel):
    """The grain of the processed zone: one site measurement."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    measurement_id: MeasurementId
    timestamp: datetime
    lot_id: LotId
    wafer_id: WaferId
    slot: int
    site_id: SiteId
    site_x_mm: float
    site_y_mm: float
    parameter_id: ParameterId
    value: float
    unit: UnitSymbol
    step_id: StepId
    tool_id: ToolId
    chamber_id: ChamberId
    recipe_id: RecipeId
    product_id: ProductId
    metrology_tool_id: MetrologyToolId
    measurement_status: MeasurementStatus
    data_revision: DataRevision

    @field_validator("timestamp")
    @classmethod
    def _timestamp_aware(cls, value: datetime) -> datetime:
        return require_aware(value, field_name="timestamp")

    @field_validator("slot")
    @classmethod
    def _slot_range(cls, value: int) -> int:
        slot_min = 1
        slot_max = 25
        if value < slot_min or value > slot_max:
            raise DomainInvariantError(
                "slot must be in 1..25",
                slot=value,
            )
        return value
