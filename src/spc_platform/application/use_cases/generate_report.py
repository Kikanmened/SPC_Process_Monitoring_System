"""Assemble and render approved report types (FR-RP01 - FR-RP03, FR-RP05)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.ports.measurement_repository import SeriesQuery
from spc_platform.application.ports.report_renderer import RenderTarget, ReportArtefact
from spc_platform.application.reporting.models import (
    ReportModel,
    ReportStatistic,
    ReportWaferMapPayload,
)
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.application.use_cases.generate_capability_report import (
    generate_capability_report,
)
from spc_platform.application.use_cases.get_wafer_map import get_wafer_map
from spc_platform.application.use_cases.run_gauge_study import run_gauge_study
from spc_platform.common.errors import InsufficientDataError
from spc_platform.common.provenance import capture_provenance
from spc_platform.common.types import FloatArray
from spc_platform.domain.enums import ReportType
from spc_platform.domain.ids import (
    ActorId,
    DataRevision,
    ExcursionId,
    LotId,
    ParameterId,
    ProductId,
    WaferId,
)
from spc_platform.domain.wafer_map_view import WaferMapView


@dataclass(frozen=True, slots=True)
class GenerateReportRequest:
    """Parameters that identify which report to build."""

    report_type: ReportType
    parameter_id: ParameterId
    product_id: ProductId | None = None
    lot_id: LotId | None = None
    wafer_id: WaferId | None = None
    excursion_id: ExcursionId | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    target: RenderTarget = RenderTarget.HTML
    include_wafer_map: bool = False
    gauge_measurements: FloatArray | None = None
    gauge_acceptable_percent: float = 10.0
    gauge_marginal_percent: float = 30.0
    gauge_minimum_distinct_categories: int = 5
    gauge_tolerance: float | None = None
    data_revision: DataRevision | None = None


def generate_report(
    services: ApplicationServices,
    *,
    actor: ActorId,
    request: GenerateReportRequest,
) -> ReportArtefact:
    """Build a report model from existing use-case results and render it."""
    services.auth.require(actor, ProtectedAction.GENERATE_REPORT)
    model = _build_model(services, actor=actor, request=request)
    artefact = services.report_renderer.render(model, request.target)
    write_audit(
        services,
        event_type=AuditEventType.REPORT_GENERATED,
        actor=actor,
        reason=f"{request.report_type.value} artefact",
        after={
            "report_type": request.report_type.value,
            "target": request.target.value,
            "parameter_id": str(request.parameter_id),
            "bytes": len(artefact.content),
        },
        data_revision=model.provenance.data_revision,
    )
    return artefact


def _build_model(
    services: ApplicationServices,
    *,
    actor: ActorId,
    request: GenerateReportRequest,
) -> ReportModel:
    if request.report_type is ReportType.SPC_SUMMARY:
        return _spc_summary(services, actor=actor, request=request)
    if request.report_type is ReportType.CAPABILITY_STUDY:
        return _capability_study(services, actor=actor, request=request)
    if request.report_type is ReportType.MSA_REPORT:
        return _msa_report(services, actor=actor, request=request)
    if request.report_type is ReportType.EXCURSION_SUMMARY:
        return _excursion_summary(services, actor=actor, request=request)
    raise InsufficientDataError(
        "unsupported report type",
        report_type=request.report_type.value,
    )


def _window_label(start: datetime, end: datetime) -> str:
    return f"{start.isoformat()} → {end.isoformat()}"


def _wafer_payload(view: WaferMapView) -> ReportWaferMapPayload:
    sites = view.sites
    if view.is_aggregated:
        xs = tuple(bin_.x_mm for bin_ in view.aggregated)
        ys = tuple(bin_.y_mm for bin_ in view.aggregated)
        zs = tuple(bin_.mean_value for bin_ in view.aggregated)
    else:
        xs = tuple(site.x_mm for site in sites)
        ys = tuple(site.y_mm for site in sites)
        zs = tuple(site.value for site in sites)
    return ReportWaferMapPayload(
        parameter_id=str(view.parameter_id),
        unit=str(view.unit),
        x=xs,
        y=ys,
        z=zs,
        vmin=view.colour_scale.vmin,
        vmax=view.colour_scale.vmax,
        n_sites_total=view.n_sites_total,
        mode=view.colour_scale.mode.value,
        aggregation_message=view.aggregation_message,
    )


def _optional_wafer_map(
    services: ApplicationServices,
    *,
    actor: ActorId,
    request: GenerateReportRequest,
) -> ReportWaferMapPayload | None:
    if not request.include_wafer_map or request.wafer_id is None or request.lot_id is None:
        return None
    view = get_wafer_map(
        services,
        actor=actor,
        parameter_id=request.parameter_id,
        lot_id=request.lot_id,
        wafer_id=request.wafer_id,
        product_id=request.product_id,
    )
    return _wafer_payload(view)


def _spc_summary(
    services: ApplicationServices,
    *,
    actor: ActorId,
    request: GenerateReportRequest,
) -> ReportModel:
    if request.window_start is None or request.window_end is None:
        raise InsufficientDataError("SPC summary requires a window")
    series = services.measurements.series_for(
        SeriesQuery(
            parameter_id=request.parameter_id,
            window_start=request.window_start,
            window_end=request.window_end,
            product_id=request.product_id,
            lot_id=request.lot_id,
        )
    )
    open_items = services.violations.list_open(request.parameter_id)
    ocap = services.control_plans.ocap_for(request.parameter_id, request.product_id)
    statistics = (
        ReportStatistic(
            label="n_observations",
            value=str(len(series.measurements)),
            n=len(series.measurements),
            window_label=_window_label(request.window_start, request.window_end),
        ),
        ReportStatistic(
            label="open_violations",
            value=str(len(open_items)),
            n=len(open_items),
            window_label="open violations",
        ),
    )
    violations = [
        {
            "rule_id": str(item.violation.rule_id),
            "timestamp": item.violation.timestamp.isoformat(),
            "statistic_value": item.violation.statistic_value,
            "ocap_id": None if ocap is None else str(ocap),
        }
        for item in open_items
    ]
    violations.sort(key=lambda row: (row["timestamp"], row["rule_id"]))
    provenance = capture_provenance(
        data_revision=series.data_revision,
        code_revision=services.code_revision,
        config_revision=services.config_revision,
        clock=services.clock,
    )
    return ReportModel(
        report_type=ReportType.SPC_SUMMARY,
        title=f"SPC summary — {request.parameter_id}",
        provenance=provenance,
        parameters={
            "parameter_id": str(request.parameter_id),
            "product_id": "" if request.product_id is None else str(request.product_id),
        },
        statistics=statistics,
        narrative=(
            "Summary assembled from stored measurements and open violations.",
            "No statistic is computed in the report renderer.",
        ),
        sections={"violations": violations},
        wafer_map=_optional_wafer_map(services, actor=actor, request=request),
        generated_at=services.clock.now(),
    )


def _capability_study(
    services: ApplicationServices,
    *,
    actor: ActorId,
    request: GenerateReportRequest,
) -> ReportModel:
    if request.product_id is None or request.window_start is None or request.window_end is None:
        raise InsufficientDataError("capability study requires product_id and window")
    outcome = generate_capability_report(
        services,
        actor=actor,
        parameter_id=request.parameter_id,
        product_id=request.product_id,
        window_start=request.window_start,
        window_end=request.window_end,
    )
    if outcome.result is None:
        raise InsufficientDataError("capability result unavailable after generation")
    result = outcome.result
    n = int(result.n_observations)
    window = _window_label(request.window_start, request.window_end)
    estimator = result.within.estimator.value
    statistics = (
        ReportStatistic(
            label="Cp",
            value="uncomputable" if result.within.cp is None else f"{result.within.cp:.4f}",
            n=n,
            window_label=window,
            estimator=estimator,
        ),
        ReportStatistic(
            label="Cpk",
            value=f"{result.within.cpk:.4f}",
            n=n,
            window_label=window,
            estimator=estimator,
        ),
        ReportStatistic(
            label="Pp",
            value="uncomputable" if result.overall.cp is None else f"{result.overall.cp:.4f}",
            n=n,
            window_label=window,
            estimator=result.overall.estimator.value,
        ),
        ReportStatistic(
            label="Ppk",
            value=f"{result.overall.cpk:.4f}",
            n=n,
            window_label=window,
            estimator=result.overall.estimator.value,
        ),
    )
    series = services.measurements.series_for(
        SeriesQuery(
            parameter_id=request.parameter_id,
            window_start=request.window_start,
            window_end=request.window_end,
            product_id=request.product_id,
        )
    )
    provenance = capture_provenance(
        data_revision=series.data_revision,
        code_revision=services.code_revision,
        config_revision=services.config_revision,
        clock=services.clock,
    )
    return ReportModel(
        report_type=ReportType.CAPABILITY_STUDY,
        title=f"Capability study — {request.parameter_id}",
        provenance=provenance,
        parameters={
            "parameter_id": str(request.parameter_id),
            "product_id": str(request.product_id),
        },
        statistics=statistics,
        narrative=("Capability indices from generate_capability_report (FR-P04).",),
        sections={"stability": result.stability.value},
        wafer_map=_optional_wafer_map(services, actor=actor, request=request),
        generated_at=services.clock.now(),
    )


def _msa_report(
    services: ApplicationServices,
    *,
    actor: ActorId,
    request: GenerateReportRequest,
) -> ReportModel:
    if request.gauge_measurements is None:
        raise InsufficientDataError(
            "MSA report requires gauge_measurements array (parts x operators x replicates)",
            parameter_id=str(request.parameter_id),
        )
    outcome = run_gauge_study(
        services,
        actor=actor,
        measurements=request.gauge_measurements,
        acceptable_percent=request.gauge_acceptable_percent,
        marginal_percent=request.gauge_marginal_percent,
        minimum_distinct_categories=request.gauge_minimum_distinct_categories,
        tolerance=request.gauge_tolerance,
        reason="msa report",
    )
    n = outcome.result.n_parts * outcome.result.n_operators * outcome.result.n_replicates
    statistics = (
        ReportStatistic(
            label="%GRR (study variation)",
            value=f"{outcome.judgement.percent_study_variation:.2f}",
            n=n,
            window_label="gauge study design",
            estimator="anova_gauge_rr",
        ),
        ReportStatistic(
            label="ndc",
            value=str(outcome.judgement.number_of_distinct_categories),
            n=n,
            window_label="gauge study design",
            estimator="anova_gauge_rr",
        ),
    )
    revision = request.data_revision or DataRevision("gauge-study")
    provenance = capture_provenance(
        data_revision=revision,
        code_revision=services.code_revision,
        config_revision=services.config_revision,
        clock=services.clock,
    )
    return ReportModel(
        report_type=ReportType.MSA_REPORT,
        title=f"MSA report — {request.parameter_id}",
        provenance=provenance,
        parameters={"parameter_id": str(request.parameter_id)},
        statistics=statistics,
        narrative=("MSA statistics from run_gauge_study; renderer computes nothing.",),
        sections={"judgement": outcome.judgement.verdict.value},
        generated_at=services.clock.now(),
    )


def _excursion_summary(
    services: ApplicationServices,
    *,
    actor: ActorId,
    request: GenerateReportRequest,
) -> ReportModel:
    if request.excursion_id is None:
        raise InsufficientDataError("excursion summary requires excursion_id")
    excursion = services.excursions.get(request.excursion_id)
    if excursion is None:
        raise InsufficientDataError(
            "unknown excursion",
            excursion_id=str(request.excursion_id),
        )
    dispositions = []
    for lot_id in excursion.lot_ids:
        for item in services.dispositions.list_for(lot_id):
            dispositions.append(
                {
                    "lot_id": str(item.lot_id),
                    "action": item.action.value,
                    "actor": str(item.actor),
                    "reason": item.reason,
                }
            )
    dispositions.sort(key=lambda row: (row["lot_id"], row["action"], row["actor"]))
    data_revision = request.data_revision or DataRevision("excursion-context")
    if request.window_start is not None and request.window_end is not None:
        series = services.measurements.series_for(
            SeriesQuery(
                parameter_id=request.parameter_id,
                window_start=request.window_start,
                window_end=request.window_end,
                product_id=request.product_id,
            )
        )
        data_revision = series.data_revision
    provenance = capture_provenance(
        data_revision=data_revision,
        code_revision=services.code_revision,
        config_revision=services.config_revision,
        clock=services.clock,
    )
    statistics = (
        ReportStatistic(
            label="violation_count",
            value=str(len(excursion.violation_ids)),
            n=len(excursion.violation_ids),
            window_label="excursion violations",
        ),
        ReportStatistic(
            label="disposition_count",
            value=str(len(dispositions)),
            n=len(dispositions),
            window_label="linked lots",
        ),
    )
    return ReportModel(
        report_type=ReportType.EXCURSION_SUMMARY,
        title=f"Excursion summary — {excursion.excursion_id}",
        provenance=provenance,
        parameters={
            "excursion_id": str(excursion.excursion_id),
            "parameter_id": str(excursion.parameter_id),
        },
        statistics=statistics,
        narrative=(
            f"State: {excursion.state.value}.",
            excursion.containment_note or "No containment note.",
            excursion.investigation_summary or "No investigation summary.",
        ),
        sections={
            "excursion_id": str(excursion.excursion_id),
            "state": excursion.state.value,
            "ocap_id": None if excursion.ocap_id is None else str(excursion.ocap_id),
            "capa_id": None if excursion.capa_id is None else str(excursion.capa_id),
            "eight_d_id": None if excursion.eight_d_id is None else str(excursion.eight_d_id),
            "dispositions": dispositions,
        },
        wafer_map=_optional_wafer_map(services, actor=actor, request=request),
        generated_at=services.clock.now(),
    )
