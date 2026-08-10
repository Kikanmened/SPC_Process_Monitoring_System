"""Report content models — numbers come from use cases, never from templates."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from spc_platform.common.provenance import Provenance
from spc_platform.common.time import require_aware
from spc_platform.domain.enums import ReportType


class ReportStatistic(BaseModel):
    """One displayed statistic with mandatory n and window (NFR-U04)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1)
    value: str
    n: int = Field(ge=0)
    window_label: str = Field(min_length=1)
    estimator: str | None = None


class ReportWaferMapPayload(BaseModel):
    """Serialised ``WaferMapView`` series for report figures (FR-RP05)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: str
    unit: str
    x: tuple[float, ...]
    y: tuple[float, ...]
    z: tuple[float, ...]
    vmin: float
    vmax: float
    n_sites_total: int
    mode: str
    aggregation_message: str | None = None


class ReportModel(BaseModel):
    """Fully qualified report content ready for HTML/PDF rendering."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_type: ReportType
    title: str = Field(min_length=1)
    provenance: Provenance
    parameters: dict[str, str] = Field(default_factory=dict)
    statistics: tuple[ReportStatistic, ...] = ()
    narrative: tuple[str, ...] = ()
    sections: dict[str, Any] = Field(default_factory=dict)
    wafer_map: ReportWaferMapPayload | None = None
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return require_aware(value, field_name="generated_at")
