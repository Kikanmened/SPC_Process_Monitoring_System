"""REST routes for the seven Phase 11 use cases."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter

from spc_platform.api.deps import ActorDep, ServicesDep
from spc_platform.api.schemas import (
    AcknowledgeViolationRequest,
    AcknowledgeViolationResponse,
    CapabilityReportRequest,
    CapabilityReportResponse,
    EvaluateLotRequest,
    EvaluateLotResponse,
    GaugeStudyRequest,
    GaugeStudyResponse,
    RecomputeBaselineRequest,
    RecomputeBaselineResponse,
    RecordDispositionRequest,
    RecordDispositionResponse,
    WaferMapRequest,
    WaferMapResponse,
    WaferSiteResponse,
)
from spc_platform.application.use_cases import (
    acknowledge_violation,
    evaluate_lot,
    generate_capability_report,
    get_wafer_map,
    recompute_baseline,
    record_disposition,
    run_gauge_study,
)
from spc_platform.common.errors import SPCPlatformError
from spc_platform.domain.ids import (
    LotId,
    OcapId,
    ParameterId,
    ProductId,
    WaferId,
)

router = APIRouter(prefix="/v1")


@router.post("/lots/evaluate", response_model=EvaluateLotResponse)
def post_evaluate_lot(
    body: EvaluateLotRequest,
    services: ServicesDep,
    actor: ActorDep,
) -> EvaluateLotResponse:
    """Evaluate a lot and persist any rule violations."""
    result = evaluate_lot(
        services,
        actor=actor,
        parameter_id=ParameterId(body.parameter_id),
        lot_id=LotId(body.lot_id),
        window_start=body.window_start,
        window_end=body.window_end,
    )
    return EvaluateLotResponse(
        baseline_id=result.baseline_id,
        points_evaluated=result.points_evaluated,
        violation_ids=[item.violation_id for item in result.violations],
    )


@router.post("/baselines/recompute", response_model=RecomputeBaselineResponse)
def post_recompute_baseline(
    body: RecomputeBaselineRequest,
    services: ServicesDep,
    actor: ActorDep,
) -> RecomputeBaselineResponse:
    """Recompute (and optionally activate) a baseline."""
    result = recompute_baseline(
        services,
        actor=actor,
        parameter_id=ParameterId(body.parameter_id),
        window_start=body.window_start,
        window_end=body.window_end,
        activate=body.activate,
        reason=body.reason,
    )
    return RecomputeBaselineResponse(
        baseline_id=str(result.baseline.baseline_id),
        status=result.baseline.status.value,
        previous_active_id=result.previous_active_id,
        n_observations=result.baseline.n_observations,
    )


@router.post("/violations/acknowledge", response_model=AcknowledgeViolationResponse)
def post_acknowledge_violation(
    body: AcknowledgeViolationRequest,
    services: ServicesDep,
    actor: ActorDep,
) -> AcknowledgeViolationResponse:
    """Acknowledge an open violation."""
    updated = acknowledge_violation(
        services,
        actor=actor,
        violation_id=body.violation_id,
        reason=body.reason,
    )
    return AcknowledgeViolationResponse(
        violation_id=updated.violation_id,
        acknowledged=updated.acknowledged,
        acknowledged_by=None if updated.acknowledged_by is None else str(updated.acknowledged_by),
    )


@router.post("/dispositions", response_model=RecordDispositionResponse)
def post_record_disposition(
    body: RecordDispositionRequest,
    services: ServicesDep,
    actor: ActorDep,
) -> RecordDispositionResponse:
    """Record a disposition with a mandatory reason."""
    disposition = record_disposition(
        services,
        actor=actor,
        lot_id=LotId(body.lot_id),
        action=body.action,
        reason=body.reason,
        ocap_id=None if body.ocap_id is None else OcapId(body.ocap_id),
    )
    return RecordDispositionResponse(
        lot_id=str(disposition.lot_id),
        action=disposition.action.value,
        actor=str(disposition.actor),
        timestamp=disposition.timestamp,
    )


@router.post("/reports/capability", response_model=CapabilityReportResponse)
def post_capability_report(
    body: CapabilityReportRequest,
    services: ServicesDep,
    actor: ActorDep,
) -> CapabilityReportResponse:
    """Generate a capability report, or refuse when out of control (FR-P04)."""
    outcome = generate_capability_report(
        services,
        actor=actor,
        parameter_id=ParameterId(body.parameter_id),
        product_id=ProductId(body.product_id),
        window_start=body.window_start,
        window_end=body.window_end,
    )
    if outcome.result is None:
        raise SPCPlatformError("capability report returned no result")
    indices = outcome.result.within
    performance = outcome.result.overall
    return CapabilityReportResponse(
        n_observations=outcome.result.n_observations,
        stability=outcome.result.stability.value,
        cp=indices.cp,
        cpk=indices.cpk,
        pp=performance.cp,
        ppk=performance.cpk,
    )


@router.post("/msa/gauge-study", response_model=GaugeStudyResponse)
def post_gauge_study(
    body: GaugeStudyRequest,
    services: ServicesDep,
    actor: ActorDep,
) -> GaugeStudyResponse:
    """Run a crossed gauge R&R study."""
    outcome = run_gauge_study(
        services,
        actor=actor,
        measurements=np.asarray(body.measurements, dtype=np.float64),
        acceptable_percent=body.acceptable_percent,
        marginal_percent=body.marginal_percent,
        minimum_distinct_categories=body.minimum_distinct_categories,
        tolerance=body.tolerance,
        reason=body.reason,
    )
    return GaugeStudyResponse(
        percent_study_variation=outcome.result.percent_study_variation,
        percent_tolerance=outcome.result.percent_tolerance,
        number_of_distinct_categories=outcome.result.number_of_distinct_categories,
        verdict=outcome.judgement.verdict.value,
        deciding_criterion=outcome.judgement.deciding_criterion.value,
    )


@router.post("/wafers/map", response_model=WaferMapResponse)
def post_wafer_map(
    body: WaferMapRequest,
    services: ServicesDep,
    actor: ActorDep,
) -> WaferMapResponse:
    """Return a wafer map view DTO (no rendering)."""
    view = get_wafer_map(
        services,
        actor=actor,
        parameter_id=ParameterId(body.parameter_id),
        lot_id=LotId(body.lot_id),
        wafer_id=WaferId(body.wafer_id),
        classify_spatial=body.classify_spatial,
    )
    return WaferMapResponse(
        parameter_id=str(view.parameter_id),
        lot_id=str(view.lot_id),
        wafer_id=str(view.wafer_id),
        sites=[
            WaferSiteResponse(
                site_id=site.site_id,
                x_mm=site.x_mm,
                y_mm=site.y_mm,
                value=site.value,
                unit=str(site.unit),
            )
            for site in view.sites
        ],
        spatial_signature=None if view.spatial_signature is None else view.spatial_signature.value,
        spatial_statistic=view.spatial_statistic,
    )
