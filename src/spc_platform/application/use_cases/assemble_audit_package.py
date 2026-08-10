"""Assemble a self-contained audit package (FR-RP04)."""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any

from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.ports.measurement_repository import SeriesQuery
from spc_platform.application.ports.report_renderer import RenderTarget, ReportArtefact
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.application.use_cases.build_chart_view import build_chart_view
from spc_platform.application.use_cases.generate_report import (
    GenerateReportRequest,
    generate_report,
)
from spc_platform.common.errors import InsufficientDataError
from spc_platform.common.provenance import Provenance, capture_provenance
from spc_platform.domain.enums import ReportType
from spc_platform.domain.ids import ActorId, ExcursionId, LotId, ParameterId, ProductId


@dataclass(frozen=True, slots=True)
class AuditPackageArtefact:
    """Zip bytes plus a content digest for independent verification."""

    content: bytes
    content_sha256: str
    provenance: Provenance
    media_type: str = "application/zip"


def assemble_audit_package(  # noqa: PLR0913 — package boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_id: ParameterId,
    product_id: ProductId,
    window_start: datetime,
    window_end: datetime,
    lot_id: LotId | None = None,
    excursion_id: ExcursionId | None = None,
) -> AuditPackageArtefact:
    """Bundle charts, data extract, limits, config revision, and dispositions."""
    services.auth.require(actor, ProtectedAction.ASSEMBLE_AUDIT_PACKAGE)
    series = services.measurements.series_for(
        SeriesQuery(
            parameter_id=parameter_id,
            window_start=window_start,
            window_end=window_end,
            product_id=product_id,
            lot_id=lot_id,
        )
    )
    baseline = services.baselines.active_for(parameter_id)
    if baseline is None:
        raise InsufficientDataError(
            "audit package requires an active baseline",
            parameter_id=str(parameter_id),
        )
    specification = services.specifications.effective_for(
        parameter_id,
        product_id,
        at=window_end,
    )
    chart = build_chart_view(
        services,
        actor=actor,
        parameter_id=parameter_id,
        window_start=window_start,
        window_end=window_end,
        product_id=product_id,
        lot_id=lot_id,
    )
    disposition_rows: list[dict[str, Any]] = []
    lot_ids = [lot_id] if lot_id is not None else []
    if excursion_id is not None:
        excursion = services.excursions.get(excursion_id)
        if excursion is not None:
            lot_ids = list(excursion.lot_ids)
    for linked_lot in lot_ids:
        for item in services.dispositions.list_for(linked_lot):
            disposition_rows.append(
                {
                    "lot_id": str(item.lot_id),
                    "action": item.action.value,
                    "actor": str(item.actor),
                    "timestamp": item.timestamp.isoformat(),
                    "reason": item.reason,
                    "ocap_id": None if item.ocap_id is None else str(item.ocap_id),
                }
            )
    disposition_rows.sort(key=lambda row: (row["lot_id"], row["timestamp"]))

    reports: list[ReportArtefact] = [
        generate_report(
            services,
            actor=actor,
            request=GenerateReportRequest(
                report_type=ReportType.SPC_SUMMARY,
                parameter_id=parameter_id,
                product_id=product_id,
                lot_id=lot_id,
                window_start=window_start,
                window_end=window_end,
                target=RenderTarget.HTML,
            ),
        )
    ]
    if excursion_id is not None:
        reports.append(
            generate_report(
                services,
                actor=actor,
                request=GenerateReportRequest(
                    report_type=ReportType.EXCURSION_SUMMARY,
                    parameter_id=parameter_id,
                    product_id=product_id,
                    excursion_id=excursion_id,
                    window_start=window_start,
                    window_end=window_end,
                    target=RenderTarget.HTML,
                ),
            )
        )

    provenance = capture_provenance(
        data_revision=series.data_revision,
        code_revision=services.code_revision,
        config_revision=services.config_revision,
        clock=services.clock,
    )
    data_extract = [
        {
            "timestamp": item.timestamp.isoformat(),
            "value": item.value,
            "lot_id": str(item.lot_id),
            "wafer_id": str(item.wafer_id),
            "site_id": int(item.site_id),
            "data_revision": str(item.data_revision),
        }
        for item in series.measurements
    ]
    limits_in_force = {
        "baseline_id": str(baseline.baseline_id),
        "centre_line": baseline.limits.centre_line,
        "sigma_estimate": baseline.limits.sigma_estimate,
        "sigma_estimator": baseline.limits.sigma_estimator.value,
        "specification": None
        if specification is None
        else {
            "lsl": specification.lsl,
            "usl": specification.usl,
            "target": specification.target,
        },
    }
    chart_payload = {
        "parameter_id": str(chart.parameter_id),
        "n_points": len(chart.points),
        "points": [
            {
                "index": point.index,
                "value": point.value,
                "timestamp": point.timestamp.isoformat(),
                "violated": point.violated,
                "rule_ids": list(point.rule_ids),
            }
            for point in chart.points
        ],
        "centre_line": chart.centre_line,
        "ucl": chart.ucl,
        "lcl": chart.lcl,
    }
    manifest = {
        "provenance": {
            "data_revision": str(provenance.data_revision),
            "code_revision": str(provenance.code_revision),
            "config_revision": str(provenance.config_revision),
            "recorded_at": provenance.recorded_at.isoformat(),
        },
        "parameter_id": str(parameter_id),
        "product_id": str(product_id),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "files": sorted(
            [
                "manifest.json",
                "data_extract.json",
                "limits_in_force.json",
                "chart.json",
                "dispositions.json",
                *[f"reports/{item.report_type.value}.html" for item in reports],
            ]
        ),
    }
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        )
        archive.writestr(
            "data_extract.json",
            json.dumps(data_extract, sort_keys=True, indent=2) + "\n",
        )
        archive.writestr(
            "limits_in_force.json",
            json.dumps(limits_in_force, sort_keys=True, indent=2) + "\n",
        )
        archive.writestr(
            "chart.json",
            json.dumps(chart_payload, sort_keys=True, indent=2) + "\n",
        )
        archive.writestr(
            "dispositions.json",
            json.dumps(disposition_rows, sort_keys=True, indent=2) + "\n",
        )
        for report in reports:
            archive.writestr(
                f"reports/{report.report_type.value}.html",
                report.content.decode("utf-8"),
            )
    content = buffer.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    write_audit(
        services,
        event_type=AuditEventType.AUDIT_PACKAGE_ASSEMBLED,
        actor=actor,
        reason="audit package assembled",
        after={
            "parameter_id": str(parameter_id),
            "content_sha256": digest,
            "bytes": len(content),
        },
        data_revision=series.data_revision,
    )
    return AuditPackageArtefact(
        content=content,
        content_sha256=digest,
        provenance=provenance,
    )
