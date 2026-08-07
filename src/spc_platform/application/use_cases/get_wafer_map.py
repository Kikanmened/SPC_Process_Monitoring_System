"""Assemble a WaferMapView for interactive and static renderers (ADR-0018)."""

from __future__ import annotations

import math

import numpy as np

from spc_platform.analytics.spatial import WaferField, classify_spatial_signature
from spc_platform.analytics.spatial.field import MIN_SITES_FOR_SIGNATURE
from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.ports.measurement_repository import WaferQuery
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.common.errors import InsufficientDataError, ViewDataUnavailableError
from spc_platform.domain.enums import MeasurementStatus
from spc_platform.domain.ids import ActorId, LotId, ParameterId, ProductId, WaferId
from spc_platform.domain.wafer_map_view import (
    MARKER_BUDGET,
    AggregatedBin,
    ColourScaleKind,
    ColourScaleLimits,
    ColourScaleMode,
    WaferGeometry,
    WaferMapView,
    WaferSiteView,
)


def get_wafer_map(  # noqa: PLR0913 — use-case boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_id: ParameterId,
    lot_id: LotId,
    wafer_id: WaferId,
    classify_spatial: bool = False,
    colour_vmin: float | None = None,
    colour_vmax: float | None = None,
    autoscale: bool = False,
    product_id: ProductId | None = None,
) -> WaferMapView:
    """Return a render-ready wafer map with fixed colour limits and budget.

    Raises ``ViewDataUnavailableError`` when the query lacks lot and wafer
    identity (ADR-0018 unfiltered-query rule).
    """
    services.auth.require(actor, ProtectedAction.GET_WAFER_MAP)
    if not str(lot_id).strip() or not str(wafer_id).strip():
        raise ViewDataUnavailableError(
            "wafer map query requires lot and wafer filters",
            lot_id=str(lot_id),
            wafer_id=str(wafer_id),
        )

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

    product = product_id or chartable[0].product_id
    specification = services.specifications.effective_for(
        parameter_id,
        product,
        at=services.clock.now(),
    )
    target = None if specification is None else specification.target

    site_views = tuple(
        WaferSiteView(
            site_id=int(item.site_id),
            x_mm=item.site_x_mm,
            y_mm=item.site_y_mm,
            value=item.value,
            unit=item.unit,
            slot=item.slot,
            tool_id=item.tool_id,
            chamber_id=item.chamber_id,
            deviation_from_target=None if target is None else item.value - target,
        )
        for item in chartable
    )

    values = np.asarray([item.value for item in chartable], dtype=np.float64)
    if autoscale:
        vmin = float(np.min(values))
        vmax = float(np.max(values))
        mode = ColourScaleMode.AUTOSCALE_LABELLED
    elif colour_vmin is not None and colour_vmax is not None:
        if colour_vmin >= colour_vmax:
            raise ViewDataUnavailableError(
                "colour scale limits must satisfy vmin < vmax",
                vmin=colour_vmin,
                vmax=colour_vmax,
            )
        vmin, vmax = colour_vmin, colour_vmax
        mode = ColourScaleMode.FIXED
    else:
        # Fixed default from data range of this view; comparison sets pass
        # explicit limits so every wafer shares the same scale (FR-S03).
        vmin = float(np.min(values))
        vmax = float(np.max(values))
        if math.isclose(vmin, vmax):
            vmax = vmin + 1.0
        mode = ColourScaleMode.FIXED

    kind = ColourScaleKind.DIVERGING_TARGET if target is not None else ColourScaleKind.VIRIDIS
    colour_scale = ColourScaleLimits(
        vmin=vmin,
        vmax=vmax,
        mode=mode,
        kind=kind,
        target=target,
    )

    is_aggregated = len(site_views) > MARKER_BUDGET
    aggregation_message: str | None = None
    aggregated: tuple[AggregatedBin, ...] = ()
    render_sites = site_views
    if is_aggregated:
        aggregated = _aggregate_sites(site_views)
        render_sites = ()
        aggregation_message = (
            f"Aggregated {len(site_views)} sites into {len(aggregated)} bins "
            f"(marker budget {MARKER_BUDGET}). Individual markers are not shown."
        )

    spatial_signature = None
    spatial_statistic = None
    if classify_spatial and len(chartable) >= MIN_SITES_FOR_SIGNATURE:
        coordinates = np.asarray(
            [(item.site_x_mm, item.site_y_mm) for item in chartable],
            dtype=np.float64,
        )
        classification = classify_spatial_signature(WaferField(coordinates, values))
        spatial_signature = classification.signature
        spatial_statistic = classification.statistic

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
            "n_sites": len(site_views),
            "is_aggregated": is_aggregated,
            "colour_vmin": vmin,
            "colour_vmax": vmax,
        },
        data_revision=revision,
    )
    return WaferMapView(
        parameter_id=parameter_id,
        lot_id=lot_id,
        wafer_id=wafer_id,
        unit=chartable[0].unit,
        sites=render_sites,
        aggregated=aggregated,
        is_aggregated=is_aggregated,
        aggregation_message=aggregation_message,
        colour_scale=colour_scale,
        geometry=WaferGeometry(),
        spatial_signature=spatial_signature,
        spatial_statistic=spatial_statistic,
        target=target,
        data_revision=revision,
        n_sites_total=len(site_views),
    )


def _aggregate_sites(sites: tuple[WaferSiteView, ...]) -> tuple[AggregatedBin, ...]:
    """Bin sites onto a coarse grid when over the marker budget (FR-S06)."""
    if not sites:
        return ()
    grid = 20
    buckets: dict[tuple[int, int], list[WaferSiteView]] = {}
    for site in sites:
        key = (int(site.x_mm // grid), int(site.y_mm // grid))
        buckets.setdefault(key, []).append(site)
    bins: list[AggregatedBin] = []
    for members in buckets.values():
        xs = [item.x_mm for item in members]
        ys = [item.y_mm for item in members]
        vals = [item.value for item in members]
        bins.append(
            AggregatedBin(
                x_mm=sum(xs) / len(xs),
                y_mm=sum(ys) / len(ys),
                mean_value=sum(vals) / len(vals),
                n_sites=len(members),
            )
        )
    bins.sort(key=lambda item: (item.y_mm, item.x_mm))
    return tuple(bins)
