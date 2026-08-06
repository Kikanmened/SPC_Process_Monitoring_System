"""Load a wafer map view for rendering (no Plotly in application)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spc_platform.analytics.spatial import (
    SignatureClassification,
    WaferField,
    classify_spatial_signature,
)
from spc_platform.analytics.spatial.field import MIN_SITES_FOR_SIGNATURE
from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.ports.measurement_repository import WaferQuery
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.common.errors import InsufficientDataError
from spc_platform.domain.enums import MeasurementStatus
from spc_platform.domain.ids import ActorId, LotId, ParameterId, WaferId


@dataclass(frozen=True, slots=True)
class WaferSiteView:
    """One site for a map renderer (coordinates in millimetres)."""

    site_id: int
    x_mm: float
    y_mm: float
    value: float
    unit: str


@dataclass(frozen=True, slots=True)
class WaferMapView:
    """DTO for Phase 12 rendering — values and optional spatial classify."""

    parameter_id: str
    lot_id: str
    wafer_id: str
    sites: tuple[WaferSiteView, ...]
    spatial: SignatureClassification | None


def get_wafer_map(  # noqa: PLR0913 — use-case boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_id: ParameterId,
    lot_id: LotId,
    wafer_id: WaferId,
    classify_spatial: bool = False,
) -> WaferMapView:
    """Return site coordinates and values; optionally classify spatial signature.

    Application does not render charts (Plotly stays in the UI layer).
    """
    services.auth.require(actor, ProtectedAction.GET_WAFER_MAP)
    sites = services.measurements.sites_for(
        WaferQuery(
            parameter_id=parameter_id,
            lot_id=lot_id,
            wafer_id=wafer_id,
        )
    )
    chartable = tuple(
        item for item in sites if item.measurement_status is not MeasurementStatus.SUPERSEDED
    )
    if not chartable:
        raise InsufficientDataError(
            "no chartable sites on wafer for parameter",
            parameter_id=str(parameter_id),
            lot_id=str(lot_id),
            wafer_id=str(wafer_id),
        )

    views = tuple(
        WaferSiteView(
            site_id=int(item.site_id),
            x_mm=item.site_x_mm,
            y_mm=item.site_y_mm,
            value=item.value,
            unit=str(item.unit),
        )
        for item in chartable
    )
    spatial: SignatureClassification | None = None
    if classify_spatial and len(chartable) >= MIN_SITES_FOR_SIGNATURE:
        coordinates = np.asarray(
            [(item.site_x_mm, item.site_y_mm) for item in chartable],
            dtype=np.float64,
        )
        values = np.asarray([item.value for item in chartable], dtype=np.float64)
        spatial = classify_spatial_signature(WaferField(coordinates, values))

    revision = chartable[0].data_revision
    write_audit(
        services,
        event_type=AuditEventType.MEASUREMENT_DATA_ACCESS,
        actor=actor,
        reason="wafer map view",
        after={
            "parameter_id": str(parameter_id),
            "lot_id": str(lot_id),
            "wafer_id": str(wafer_id),
            "n_sites": len(views),
            "classified_spatial": spatial is not None,
        },
        data_revision=revision,
    )
    return WaferMapView(
        parameter_id=str(parameter_id),
        lot_id=str(lot_id),
        wafer_id=str(wafer_id),
        sites=views,
        spatial=spatial,
    )
