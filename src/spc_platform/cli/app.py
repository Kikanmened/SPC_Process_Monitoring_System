"""Typer CLI that calls the same use cases as the FastAPI routes."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Annotated

import numpy as np
import typer

from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.report_renderer import RenderTarget
from spc_platform.application.use_cases import (
    GenerateReportRequest,
    acknowledge_violation,
    assemble_audit_package,
    close_excursion,
    dispatch_notifications,
    evaluate_lot,
    generate_capability_report,
    generate_report,
    get_wafer_map,
    open_excursion,
    recompute_baseline,
    record_disposition,
    run_gauge_study,
)
from spc_platform.common.errors import SPCPlatformError
from spc_platform.domain.enums import DispositionAction, ReportType
from spc_platform.domain.ids import (
    ActorId,
    CapaId,
    EightDId,
    ExcursionId,
    LotId,
    OcapId,
    ParameterId,
    ProductId,
    WaferId,
)
from spc_platform.infrastructure.composition import LocalBundle, build_local_bundle


def create_cli(  # noqa: PLR0915 — registers use-case commands
    bundle: LocalBundle | None = None,
) -> typer.Typer:
    """Build a Typer app wired to ``bundle`` (or a fresh local fake stack)."""
    cli = typer.Typer(
        name="spc",
        help="Semiconductor SPC platform CLI — same use cases as the API.",
        no_args_is_help=True,
    )
    resolved = bundle if bundle is not None else build_local_bundle()

    def _parse_aware(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            message = "timestamps must be timezone-aware ISO-8601"
            raise typer.BadParameter(message)
        return parsed

    def _services(ctx: typer.Context) -> ApplicationServices:
        current = ctx.obj
        if not isinstance(current, LocalBundle):
            message = "CLI is not initialised with a LocalBundle"
            raise RuntimeError(message)
        return current.services

    def _actor(ctx: typer.Context) -> ActorId:
        return ActorId(str(ctx.meta["actor"]))

    @cli.callback()
    def _root(
        ctx: typer.Context,
        actor: Annotated[
            str,
            typer.Option("--actor", envvar="SPC_ACTOR", help="Acting identity"),
        ] = "cli.operator",
    ) -> None:
        """Attach the composition root and acting identity."""
        ctx.obj = resolved
        ctx.meta["actor"] = ActorId(actor)

    @cli.command("evaluate-lot")
    def cmd_evaluate_lot(
        ctx: typer.Context,
        parameter_id: Annotated[str, typer.Option()],
        lot_id: Annotated[str, typer.Option()],
        window_start: Annotated[str, typer.Option()],
        window_end: Annotated[str, typer.Option()],
    ) -> None:
        """Evaluate a lot against the active baseline."""
        try:
            result = evaluate_lot(
                _services(ctx),
                actor=_actor(ctx),
                parameter_id=ParameterId(parameter_id),
                lot_id=LotId(lot_id),
                window_start=_parse_aware(window_start),
                window_end=_parse_aware(window_end),
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        typer.echo(
            json.dumps(
                {
                    "baseline_id": result.baseline_id,
                    "points_evaluated": result.points_evaluated,
                    "violation_ids": [item.violation_id for item in result.violations],
                }
            )
        )

    @cli.command("recompute-baseline")
    def cmd_recompute_baseline(  # noqa: PLR0913,PLR0917
        ctx: typer.Context,
        parameter_id: Annotated[str, typer.Option()],
        window_start: Annotated[str, typer.Option()],
        window_end: Annotated[str, typer.Option()],
        activate: Annotated[bool, typer.Option()] = False,
        reason: Annotated[str, typer.Option()] = "",
    ) -> None:
        """Recompute a baseline over a window."""
        try:
            result = recompute_baseline(
                _services(ctx),
                actor=_actor(ctx),
                parameter_id=ParameterId(parameter_id),
                window_start=_parse_aware(window_start),
                window_end=_parse_aware(window_end),
                activate=activate,
                reason=reason,
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        typer.echo(
            json.dumps(
                {
                    "baseline_id": str(result.baseline.baseline_id),
                    "status": result.baseline.status.value,
                    "previous_active_id": result.previous_active_id,
                    "n_observations": result.baseline.n_observations,
                }
            )
        )

    @cli.command("acknowledge-violation")
    def cmd_acknowledge_violation(
        ctx: typer.Context,
        violation_id: Annotated[str, typer.Option()],
        reason: Annotated[str, typer.Option()] = "",
    ) -> None:
        """Acknowledge an open violation."""
        try:
            updated = acknowledge_violation(
                _services(ctx),
                actor=_actor(ctx),
                violation_id=violation_id,
                reason=reason,
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        typer.echo(
            json.dumps(
                {
                    "violation_id": updated.violation_id,
                    "acknowledged": updated.acknowledged,
                    "acknowledged_by": None
                    if updated.acknowledged_by is None
                    else str(updated.acknowledged_by),
                }
            )
        )

    @cli.command("record-disposition")
    def cmd_record_disposition(
        ctx: typer.Context,
        lot_id: Annotated[str, typer.Option()],
        action: Annotated[DispositionAction, typer.Option()],
        reason: Annotated[str, typer.Option()],
        ocap_id: Annotated[str | None, typer.Option()] = None,
    ) -> None:
        """Record a material disposition."""
        try:
            disposition = record_disposition(
                _services(ctx),
                actor=_actor(ctx),
                lot_id=LotId(lot_id),
                action=action,
                reason=reason,
                ocap_id=None if ocap_id is None else OcapId(ocap_id),
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        typer.echo(
            json.dumps(
                {
                    "lot_id": str(disposition.lot_id),
                    "action": disposition.action.value,
                    "actor": str(disposition.actor),
                    "timestamp": disposition.timestamp.isoformat(),
                }
            )
        )

    @cli.command("capability-report")
    def cmd_capability_report(
        ctx: typer.Context,
        parameter_id: Annotated[str, typer.Option()],
        product_id: Annotated[str, typer.Option()],
        window_start: Annotated[str, typer.Option()],
        window_end: Annotated[str, typer.Option()],
    ) -> None:
        """Generate a capability report (refuses unstable processes)."""
        try:
            outcome = generate_capability_report(
                _services(ctx),
                actor=_actor(ctx),
                parameter_id=ParameterId(parameter_id),
                product_id=ProductId(product_id),
                window_start=_parse_aware(window_start),
                window_end=_parse_aware(window_end),
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        if outcome.result is None:
            message = "capability report returned no result"
            raise SPCPlatformError(message)
        typer.echo(
            json.dumps(
                {
                    "n_observations": outcome.result.n_observations,
                    "stability": outcome.result.stability.value,
                    "cp": outcome.result.within.cp,
                    "cpk": outcome.result.within.cpk,
                    "pp": outcome.result.overall.cp,
                    "ppk": outcome.result.overall.cpk,
                }
            )
        )

    @cli.command("gauge-study")
    def cmd_gauge_study(  # noqa: PLR0913,PLR0917
        ctx: typer.Context,
        measurements_file: Annotated[
            Path,
            typer.Option(help="JSON file: nested [parts][operators][replicates]"),
        ],
        acceptable_percent: Annotated[float, typer.Option()] = 10.0,
        marginal_percent: Annotated[float, typer.Option()] = 30.0,
        minimum_distinct_categories: Annotated[int, typer.Option()] = 5,
        tolerance: Annotated[float | None, typer.Option()] = None,
    ) -> None:
        """Run a crossed gauge R&R study from a JSON payload file."""
        payload = json.loads(measurements_file.read_text(encoding="utf-8"))
        try:
            outcome = run_gauge_study(
                _services(ctx),
                actor=_actor(ctx),
                measurements=np.asarray(payload, dtype=np.float64),
                acceptable_percent=acceptable_percent,
                marginal_percent=marginal_percent,
                minimum_distinct_categories=minimum_distinct_categories,
                tolerance=tolerance,
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        typer.echo(
            json.dumps(
                {
                    "percent_study_variation": outcome.result.percent_study_variation,
                    "percent_tolerance": outcome.result.percent_tolerance,
                    "number_of_distinct_categories": (outcome.result.number_of_distinct_categories),
                    "verdict": outcome.judgement.verdict.value,
                    "deciding_criterion": outcome.judgement.deciding_criterion.value,
                }
            )
        )

    @cli.command("wafer-map")
    def cmd_wafer_map(
        ctx: typer.Context,
        parameter_id: Annotated[str, typer.Option()],
        lot_id: Annotated[str, typer.Option()],
        wafer_id: Annotated[str, typer.Option()],
        classify_spatial: Annotated[bool, typer.Option()] = False,
    ) -> None:
        """Print a wafer map view as JSON."""
        try:
            view = get_wafer_map(
                _services(ctx),
                actor=_actor(ctx),
                parameter_id=ParameterId(parameter_id),
                lot_id=LotId(lot_id),
                wafer_id=WaferId(wafer_id),
                classify_spatial=classify_spatial,
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        typer.echo(
            json.dumps(
                {
                    "parameter_id": str(view.parameter_id),
                    "lot_id": str(view.lot_id),
                    "wafer_id": str(view.wafer_id),
                    "n_sites_total": view.n_sites_total,
                    "is_aggregated": view.is_aggregated,
                    "sites": [
                        {
                            "site_id": site.site_id,
                            "x_mm": site.x_mm,
                            "y_mm": site.y_mm,
                            "value": site.value,
                            "unit": str(site.unit),
                        }
                        for site in view.sites
                    ],
                    "spatial_signature": None
                    if view.spatial_signature is None
                    else view.spatial_signature.value,
                }
            )
        )

    @cli.command("generate-report")
    def cmd_generate_report(  # noqa: PLR0913, PLR0917 — CLI option surface
        ctx: typer.Context,
        report_type: Annotated[str, typer.Option()],
        parameter_id: Annotated[str, typer.Option()],
        window_start: Annotated[str | None, typer.Option()] = None,
        window_end: Annotated[str | None, typer.Option()] = None,
        product_id: Annotated[str | None, typer.Option()] = None,
        lot_id: Annotated[str | None, typer.Option()] = None,
        excursion_id: Annotated[str | None, typer.Option()] = None,
        target: Annotated[str, typer.Option()] = "html",
        output: Annotated[Path | None, typer.Option()] = None,
    ) -> None:
        """Render a report artefact (HTML by default)."""
        try:
            artefact = generate_report(
                _services(ctx),
                actor=_actor(ctx),
                request=GenerateReportRequest(
                    report_type=ReportType(report_type),
                    parameter_id=ParameterId(parameter_id),
                    product_id=None if product_id is None else ProductId(product_id),
                    lot_id=None if lot_id is None else LotId(lot_id),
                    excursion_id=None if excursion_id is None else ExcursionId(excursion_id),
                    window_start=None if window_start is None else _parse_aware(window_start),
                    window_end=None if window_end is None else _parse_aware(window_end),
                    target=RenderTarget(target),
                ),
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        if output is not None:
            output.write_bytes(artefact.content)
        typer.echo(
            json.dumps(
                {
                    "report_type": artefact.report_type.value,
                    "target": artefact.target.value,
                    "bytes": len(artefact.content),
                    "data_revision": str(artefact.provenance.data_revision),
                    "code_revision": str(artefact.provenance.code_revision),
                    "config_revision": str(artefact.provenance.config_revision),
                }
            )
        )

    @cli.command("open-excursion")
    def cmd_open_excursion(
        ctx: typer.Context,
        parameter_id: Annotated[str, typer.Option()],
        lot_id: Annotated[str, typer.Option()],
        violation_ids: Annotated[str, typer.Option(help="Comma-separated violation ids")],
        product_id: Annotated[str | None, typer.Option()] = None,
    ) -> None:
        """Open an excursion from one or more violations."""
        try:
            excursion = open_excursion(
                _services(ctx),
                actor=_actor(ctx),
                parameter_id=ParameterId(parameter_id),
                lot_ids=(LotId(lot_id),),
                violation_ids=tuple(
                    item.strip() for item in violation_ids.split(",") if item.strip()
                ),
                product_id=None if product_id is None else ProductId(product_id),
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        typer.echo(
            json.dumps(
                {
                    "excursion_id": str(excursion.excursion_id),
                    "state": excursion.state.value,
                    "ocap_id": None if excursion.ocap_id is None else str(excursion.ocap_id),
                }
            )
        )

    @cli.command("close-excursion")
    def cmd_close_excursion(
        ctx: typer.Context,
        excursion_id: Annotated[str, typer.Option()],
        capa_id: Annotated[str | None, typer.Option()] = None,
        eight_d_id: Annotated[str | None, typer.Option()] = None,
        reason: Annotated[str, typer.Option()] = "",
    ) -> None:
        """Close an excursion with CAPA or 8D reference."""
        try:
            excursion = close_excursion(
                _services(ctx),
                actor=_actor(ctx),
                excursion_id=ExcursionId(excursion_id),
                capa_id=None if capa_id is None else CapaId(capa_id),
                eight_d_id=None if eight_d_id is None else EightDId(eight_d_id),
                reason=reason,
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        typer.echo(
            json.dumps(
                {
                    "excursion_id": str(excursion.excursion_id),
                    "state": excursion.state.value,
                    "capa_id": None if excursion.capa_id is None else str(excursion.capa_id),
                    "eight_d_id": None
                    if excursion.eight_d_id is None
                    else str(excursion.eight_d_id),
                }
            )
        )

    @cli.command("assemble-audit-package")
    def cmd_assemble_audit_package(  # noqa: PLR0913, PLR0917 — CLI option surface
        ctx: typer.Context,
        parameter_id: Annotated[str, typer.Option()],
        product_id: Annotated[str, typer.Option()],
        window_start: Annotated[str, typer.Option()],
        window_end: Annotated[str, typer.Option()],
        output: Annotated[Path, typer.Option()],
        lot_id: Annotated[str | None, typer.Option()] = None,
        excursion_id: Annotated[str | None, typer.Option()] = None,
    ) -> None:
        """Write a self-contained audit package zip."""
        try:
            package = assemble_audit_package(
                _services(ctx),
                actor=_actor(ctx),
                parameter_id=ParameterId(parameter_id),
                product_id=ProductId(product_id),
                window_start=_parse_aware(window_start),
                window_end=_parse_aware(window_end),
                lot_id=None if lot_id is None else LotId(lot_id),
                excursion_id=None if excursion_id is None else ExcursionId(excursion_id),
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        output.write_bytes(package.content)
        typer.echo(
            json.dumps(
                {
                    "content_sha256": package.content_sha256,
                    "bytes": len(package.content),
                    "path": str(output),
                }
            )
        )

    @cli.command("dispatch-notifications")
    def cmd_dispatch_notifications(
        ctx: typer.Context,
        parameter_id: Annotated[str | None, typer.Option()] = None,
    ) -> None:
        """Dispatch one digested notification for open violations."""
        try:
            receipt = dispatch_notifications(
                _services(ctx),
                actor=_actor(ctx),
                parameter_id=None if parameter_id is None else ParameterId(parameter_id),
            )
        except SPCPlatformError as exc:
            typer.echo(json.dumps({"error": type(exc).__name__, "message": str(exc)}))
            raise typer.Exit(code=1) from exc
        typer.echo(
            json.dumps(
                {
                    "digest_id": receipt.digest_id,
                    "recipient": receipt.recipient,
                    "item_count": receipt.item_count,
                    "transport": receipt.transport,
                }
            )
        )

    return cli


app = create_cli()


def run() -> None:
    """Console-script entry point."""
    app()
