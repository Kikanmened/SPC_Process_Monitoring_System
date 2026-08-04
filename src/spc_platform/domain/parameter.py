"""A measurable process characteristic.

Carries unit and metrology method; the unit is never implicit
(SYSTEM_ARCHITECTURE.md §3.1).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.domain.enums import ChartType, SubgroupingKind
from spc_platform.domain.ids import ParameterId, UnitSymbol


class Parameter(BaseModel):
    """Registry entry for one controlled characteristic."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    name: str
    unit: UnitSymbol
    metrology_method: str
    chart_type: ChartType
    subgrouping: SubgroupingKind
    sampling_sites: int = Field(ge=1)
    description: str = ""
