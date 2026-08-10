"""Excursion lifecycle, digests, and audit packages."""

from __future__ import annotations

import zipfile
from io import BytesIO

import numpy as np
import pytest
from tests.factories.application import ACTOR, WINDOW_END, WINDOW_START, seeded_bundle

from spc_platform.application.audit import AuditEventType
from spc_platform.application.ports.report_renderer import RenderTarget
from spc_platform.application.use_cases import (
    GenerateReportRequest,
    assemble_audit_package,
    build_alarm_queue,
    close_excursion,
    contain_excursion,
    dispatch_notifications,
    evaluate_lot,
    generate_report,
    open_excursion,
    record_disposition,
    record_excursion_investigation,
)
from spc_platform.common.errors import DispositionRequiredError, InsufficientDataError
from spc_platform.domain.enums import DispositionAction, ReportType
from spc_platform.domain.excursion import Excursion
from spc_platform.domain.ids import (
    CapaId,
    LotId,
    ParameterId,
    ProductId,
)
from spc_platform.infrastructure.composition import LocalBundle


def _open_with_violation() -> tuple[LocalBundle, Excursion]:
    bundle = seeded_bundle(outlier=11.5)
    result = evaluate_lot(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        lot_id=LotId("LOT-001"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )
    assert result.violations
    excursion = open_excursion(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        lot_ids=(LotId("LOT-001"),),
        violation_ids=tuple(item.violation_id for item in result.violations),
        product_id=ProductId("DEV-A"),
    )
    return bundle, excursion


def test_alarm_queue_carries_ocap_from_control_plan() -> None:
    bundle, _ = _open_with_violation()
    queue = build_alarm_queue(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
    )
    assert queue.n_open >= 1
    assert any(item.ocap_id == "OCAP-OXIDE-THK" for item in queue.items)


def test_close_excursion_requires_disposition() -> None:
    bundle, excursion = _open_with_violation()
    with pytest.raises(DispositionRequiredError):
        close_excursion(
            bundle.services,
            actor=ACTOR,
            excursion_id=excursion.excursion_id,
            capa_id=CapaId("CAPA-1"),
        )


def test_close_excursion_requires_capa_or_eight_d() -> None:
    bundle, excursion = _open_with_violation()
    record_disposition(
        bundle.services,
        actor=ACTOR,
        lot_id=LotId("LOT-001"),
        action=DispositionAction.HOLD,
        reason="hold pending investigation",
    )
    with pytest.raises(InsufficientDataError):
        close_excursion(
            bundle.services,
            actor=ACTOR,
            excursion_id=excursion.excursion_id,
        )


def test_excursion_lifecycle_to_closure() -> None:
    bundle, excursion = _open_with_violation()
    contain_excursion(
        bundle.services,
        actor=ACTOR,
        excursion_id=excursion.excursion_id,
        note="lot held at metrology",
    )
    record_excursion_investigation(
        bundle.services,
        actor=ACTOR,
        excursion_id=excursion.excursion_id,
        summary="chamber B shared with affected lots; no cause asserted",
    )
    record_disposition(
        bundle.services,
        actor=ACTOR,
        lot_id=LotId("LOT-001"),
        action=DispositionAction.REWORK,
        reason="rework oxide",
    )
    closed = close_excursion(
        bundle.services,
        actor=ACTOR,
        excursion_id=excursion.excursion_id,
        capa_id=CapaId("CAPA-42"),
        reason="closed after disposition",
    )
    assert closed.state.value == "closed"
    assert closed.capa_id == CapaId("CAPA-42")
    assert bundle.audit.list_for(AuditEventType.EXCURSION_CLOSED)


def test_dispatch_is_one_digest_not_one_per_violation() -> None:
    bundle, _ = _open_with_violation()
    receipt = dispatch_notifications(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
    )
    assert receipt.item_count >= 1
    assert len(bundle.notifier.dispatched) == 1
    assert len(bundle.notifier.dispatched[0].items) == receipt.item_count


def test_msa_report_from_gauge_measurements() -> None:
    bundle = seeded_bundle()
    rng = np.random.default_rng(0)
    measurements = 10.0 + 0.1 * rng.normal(size=(5, 3, 2))
    artefact = generate_report(
        bundle.services,
        actor=ACTOR,
        request=GenerateReportRequest(
            report_type=ReportType.MSA_REPORT,
            parameter_id=ParameterId("OXIDE_THK"),
            gauge_measurements=measurements,
            target=RenderTarget.HTML,
        ),
    )
    html = artefact.content.decode("utf-8")
    assert "MSA report" in html
    assert "data_revision" in html


def test_audit_package_is_self_contained_zip() -> None:
    bundle = seeded_bundle()
    package = assemble_audit_package(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        product_id=ProductId("DEV-A"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        lot_id=LotId("LOT-001"),
    )
    assert package.content_sha256
    with zipfile.ZipFile(BytesIO(package.content)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "data_extract.json" in names
        assert "limits_in_force.json" in names
        assert "dispositions.json" in names
        assert "reports/spc_summary.html" in names
        manifest = archive.read("manifest.json").decode("utf-8")
        assert "data_revision" in manifest
