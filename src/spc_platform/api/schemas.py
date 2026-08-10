"""Request and response models for the Phase 11 REST surface."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.domain.enums import DispositionAction


class EvaluateLotRequest(BaseModel):
    """Evaluate a lot against the active baseline."""

    model_config = ConfigDict(extra="forbid")

    parameter_id: str
    lot_id: str
    window_start: datetime
    window_end: datetime


class EvaluateLotResponse(BaseModel):
    """Lot evaluation outcome."""

    model_config = ConfigDict(extra="forbid")

    baseline_id: str
    points_evaluated: int
    violation_ids: list[str]


class RecomputeBaselineRequest(BaseModel):
    """Recompute a baseline over a window."""

    model_config = ConfigDict(extra="forbid")

    parameter_id: str
    window_start: datetime
    window_end: datetime
    activate: bool = False
    reason: str = ""


class RecomputeBaselineResponse(BaseModel):
    """Stored baseline identity and status."""

    model_config = ConfigDict(extra="forbid")

    baseline_id: str
    status: str
    previous_active_id: str | None
    n_observations: int


class AcknowledgeViolationRequest(BaseModel):
    """Acknowledge one violation."""

    model_config = ConfigDict(extra="forbid")

    violation_id: str
    reason: str = ""


class AcknowledgeViolationResponse(BaseModel):
    """Acknowledgement confirmation."""

    model_config = ConfigDict(extra="forbid")

    violation_id: str
    acknowledged: bool
    acknowledged_by: str | None


class RecordDispositionRequest(BaseModel):
    """Record a material disposition."""

    model_config = ConfigDict(extra="forbid")

    lot_id: str
    action: DispositionAction
    reason: str = Field(min_length=1)
    ocap_id: str | None = None


class RecordDispositionResponse(BaseModel):
    """Disposition confirmation."""

    model_config = ConfigDict(extra="forbid")

    lot_id: str
    action: str
    actor: str
    timestamp: datetime


class CapabilityReportRequest(BaseModel):
    """Request a capability assessment."""

    model_config = ConfigDict(extra="forbid")

    parameter_id: str
    product_id: str
    window_start: datetime
    window_end: datetime


class CapabilityReportResponse(BaseModel):
    """Capability indices when the process is in control."""

    model_config = ConfigDict(extra="forbid")

    n_observations: int
    stability: str
    cp: float | None
    cpk: float | None
    pp: float | None
    ppk: float | None


class GaugeStudyRequest(BaseModel):
    """Balanced crossed gauge study payload."""

    model_config = ConfigDict(extra="forbid")

    measurements: list[list[list[float]]]
    acceptable_percent: float
    marginal_percent: float
    minimum_distinct_categories: int
    tolerance: float | None = None
    reason: str = ""


class GaugeStudyResponse(BaseModel):
    """Gauge R&R summary and verdict."""

    model_config = ConfigDict(extra="forbid")

    percent_study_variation: float
    percent_tolerance: float | None
    number_of_distinct_categories: int
    verdict: str
    deciding_criterion: str


class WaferMapRequest(BaseModel):
    """Load sites for one wafer/parameter."""

    model_config = ConfigDict(extra="forbid")

    parameter_id: str
    lot_id: str
    wafer_id: str
    classify_spatial: bool = False


class WaferSiteResponse(BaseModel):
    """One site on a wafer map."""

    model_config = ConfigDict(extra="forbid")

    site_id: int
    x_mm: float
    y_mm: float
    value: float
    unit: str


class WaferMapResponse(BaseModel):
    """Wafer map DTO for rendering."""

    model_config = ConfigDict(extra="forbid")

    parameter_id: str
    lot_id: str
    wafer_id: str
    sites: list[WaferSiteResponse]
    spatial_signature: str | None
    spatial_statistic: float | None


class ErrorBody(BaseModel):
    """Structured error payload."""

    model_config = ConfigDict(extra="forbid")

    error: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class GenerateReportRequestBody(BaseModel):
    """Render an approved report artefact."""

    model_config = ConfigDict(extra="forbid")

    report_type: str
    parameter_id: str
    product_id: str | None = None
    lot_id: str | None = None
    wafer_id: str | None = None
    excursion_id: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    target: str = "html"
    include_wafer_map: bool = False


class GenerateReportResponse(BaseModel):
    """Rendered report metadata and base64-safe text for HTML."""

    model_config = ConfigDict(extra="forbid")

    report_type: str
    target: str
    media_type: str
    content_text: str | None
    content_sha256: str
    data_revision: str
    code_revision: str
    config_revision: str


class OpenExcursionRequest(BaseModel):
    """Open an excursion from violations."""

    model_config = ConfigDict(extra="forbid")

    parameter_id: str
    lot_ids: list[str] = Field(min_length=1)
    violation_ids: list[str] = Field(min_length=1)
    product_id: str | None = None


class ExcursionResponse(BaseModel):
    """Excursion lifecycle snapshot."""

    model_config = ConfigDict(extra="forbid")

    excursion_id: str
    state: str
    ocap_id: str | None
    capa_id: str | None = None
    eight_d_id: str | None = None


class CloseExcursionRequest(BaseModel):
    """Close an excursion with 8D or CAPA reference."""

    model_config = ConfigDict(extra="forbid")

    excursion_id: str
    capa_id: str | None = None
    eight_d_id: str | None = None
    reason: str = ""


class AuditPackageRequest(BaseModel):
    """Assemble a self-contained audit package."""

    model_config = ConfigDict(extra="forbid")

    parameter_id: str
    product_id: str
    window_start: datetime
    window_end: datetime
    lot_id: str | None = None
    excursion_id: str | None = None


class AuditPackageResponse(BaseModel):
    """Audit package digest for verification."""

    model_config = ConfigDict(extra="forbid")

    content_sha256: str
    bytes: int
    data_revision: str
    code_revision: str
    config_revision: str


class DispatchNotificationsRequest(BaseModel):
    """Dispatch one digested notification batch."""

    model_config = ConfigDict(extra="forbid")

    parameter_id: str | None = None
    product_id: str | None = None


class DispatchNotificationsResponse(BaseModel):
    """Digest dispatch receipt."""

    model_config = ConfigDict(extra="forbid")

    digest_id: str
    recipient: str
    item_count: int
    transport: str
