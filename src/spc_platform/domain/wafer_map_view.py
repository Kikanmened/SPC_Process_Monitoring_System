"""Wafer map view model shared by interactive and static renderers (ADR-0018).

Colour scale limits, aggregation state, and geometry live on the view so Plotly
and Matplotlib cannot disagree about what they are drawing.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.domain.enums import SpatialSignature
from spc_platform.domain.ids import (
    ChamberId,
    DataRevision,
    LotId,
    ParameterId,
    ToolId,
    UnitSymbol,
    WaferId,
)

MARKER_BUDGET = 5_000
"""Hard cap on individually rendered site markers per figure (NFR-P04, ADR-0018)."""

DEFAULT_WAFER_RADIUS_MM = 150.0
"""Nominal radius of a 300 mm wafer."""

DEFAULT_EXCLUSION_MM = 3.0
"""Edge exclusion zone drawn on the map (display only)."""


class ColourScaleMode(StrEnum):
    """How colour limits were chosen for this view."""

    FIXED = "fixed"
    AUTOSCALE_LABELLED = "autoscale_labelled"


class ColourScaleKind(StrEnum):
    """Allowed perceptually uniform scales (FR-S04)."""

    VIRIDIS = "viridis"
    CIVIDIS = "cividis"
    DIVERGING_TARGET = "diverging_target"


class WaferSiteView(BaseModel):
    """One site ready for rendering (FR-S01, FR-S05)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    site_id: int
    x_mm: float
    y_mm: float
    value: float
    unit: UnitSymbol
    slot: int
    tool_id: ToolId
    chamber_id: ChamberId
    deviation_from_target: float | None = None


class ColourScaleLimits(BaseModel):
    """Fixed (or explicitly labelled autoscale) colour limits (FR-S03)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    vmin: float
    vmax: float
    mode: ColourScaleMode
    kind: ColourScaleKind
    target: float | None = None


class WaferGeometry(BaseModel):
    """Wafer boundary, notch, and exclusion for both renderers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    radius_mm: float = DEFAULT_WAFER_RADIUS_MM
    notch_angle_deg: float = -90.0
    exclusion_mm: float = DEFAULT_EXCLUSION_MM


class AggregatedBin(BaseModel):
    """One bin when the marker budget forces aggregation (FR-S06)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    x_mm: float
    y_mm: float
    mean_value: float
    n_sites: int


class WaferMapView(BaseModel):
    """One computation behind interactive Plotly and static Matplotlib export."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    lot_id: LotId
    wafer_id: WaferId
    unit: UnitSymbol
    sites: tuple[WaferSiteView, ...] = Field(default_factory=tuple)
    aggregated: tuple[AggregatedBin, ...] = Field(default_factory=tuple)
    is_aggregated: bool = False
    aggregation_message: str | None = None
    colour_scale: ColourScaleLimits
    geometry: WaferGeometry = Field(default_factory=WaferGeometry)
    spatial_signature: SpatialSignature | None = None
    spatial_statistic: float | None = None
    target: float | None = None
    data_revision: DataRevision
    n_sites_total: int = Field(ge=0)
