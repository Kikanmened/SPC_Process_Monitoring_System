"""Detection → ack → disposition → excursion summary (Module 9 e2e)."""

from __future__ import annotations

from tests.factories.application import ACTOR, WINDOW_END, WINDOW_START, seeded_bundle

from spc_platform.application.ports.report_renderer import RenderTarget
from spc_platform.application.use_cases import (
    GenerateReportRequest,
    acknowledge_violation,
    build_alarm_queue,
    close_excursion,
    contain_excursion,
    evaluate_lot,
    generate_report,
    open_excursion,
    record_disposition,
    record_excursion_investigation,
)
from spc_platform.domain.enums import DispositionAction, ReportType
from spc_platform.domain.ids import CapaId, LotId, ParameterId, ProductId


def test_violation_to_excursion_summary() -> None:
    bundle = seeded_bundle(outlier=11.5)
    evaluated = evaluate_lot(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        lot_id=LotId("LOT-001"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )
    violation_id = evaluated.violations[0].violation_id
    queue = build_alarm_queue(bundle.services, actor=ACTOR)
    assert any(item.violation_id == violation_id and item.ocap_id for item in queue.items)
    acknowledge_violation(
        bundle.services,
        actor=ACTOR,
        violation_id=violation_id,
        reason="seen on shift",
    )
    excursion = open_excursion(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        lot_ids=(LotId("LOT-001"),),
        violation_ids=(violation_id,),
        product_id=ProductId("DEV-A"),
    )
    contain_excursion(
        bundle.services,
        actor=ACTOR,
        excursion_id=excursion.excursion_id,
        note="material held",
    )
    record_excursion_investigation(
        bundle.services,
        actor=ACTOR,
        excursion_id=excursion.excursion_id,
        summary="tool ETCH-01 common; evidence only",
    )
    record_disposition(
        bundle.services,
        actor=ACTOR,
        lot_id=LotId("LOT-001"),
        action=DispositionAction.HOLD,
        reason="hold pending CAPA",
        ocap_id=excursion.ocap_id,
    )
    close_excursion(
        bundle.services,
        actor=ACTOR,
        excursion_id=excursion.excursion_id,
        capa_id=CapaId("CAPA-E2E-1"),
    )
    report = generate_report(
        bundle.services,
        actor=ACTOR,
        request=GenerateReportRequest(
            report_type=ReportType.EXCURSION_SUMMARY,
            parameter_id=ParameterId("OXIDE_THK"),
            product_id=ProductId("DEV-A"),
            excursion_id=excursion.excursion_id,
            window_start=WINDOW_START,
            window_end=WINDOW_END,
            target=RenderTarget.HTML,
        ),
    )
    html = report.content.decode("utf-8")
    assert "CAPA-E2E-1" in html
    assert "hold pending CAPA" in html
    assert "data_revision" in html
