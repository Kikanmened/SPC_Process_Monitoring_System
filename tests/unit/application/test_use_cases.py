"""Use cases against fake adapters — happy paths, refusals, audit abort."""

from __future__ import annotations

from datetime import timedelta

import numpy as np
import pytest
from tests.factories.application import (
    ACTOR,
    WINDOW_END,
    WINDOW_START,
    seeded_bundle,
)
from tests.factories.domain import a_measurement, aware

from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.use_cases import (
    acknowledge_violation,
    evaluate_lot,
    generate_capability_report,
    get_wafer_map,
    recompute_baseline,
    record_disposition,
    run_gauge_study,
)
from spc_platform.common.errors import (
    AuditWriteError,
    InsufficientDataError,
    NoActiveBaselineError,
    UnauthorisedActionError,
    UnstableProcessError,
)
from spc_platform.domain.enums import DispositionAction
from spc_platform.domain.ids import (
    DataRevision,
    LotId,
    ParameterId,
    ProductId,
    SiteId,
    WaferId,
)
from spc_platform.infrastructure.composition import build_local_bundle
from spc_platform.infrastructure.repositories.support_fakes import FakeAuthorisation


def test_evaluate_lot_raises_and_audits_violations() -> None:
    bundle = seeded_bundle(outlier=11.5)
    result = evaluate_lot(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        lot_id=LotId("LOT-001"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )
    assert result.points_evaluated >= 8
    assert len(result.violations) >= 1
    raised = bundle.audit.list_for(AuditEventType.VIOLATION_RAISED)
    assert len(raised) == len(result.violations)


def test_evaluate_lot_refuses_without_baseline() -> None:
    bundle = seeded_bundle(with_baseline=False)
    with pytest.raises(NoActiveBaselineError):
        evaluate_lot(
            bundle.services,
            actor=ACTOR,
            parameter_id=ParameterId("OXIDE_THK"),
            lot_id=LotId("LOT-001"),
            window_start=WINDOW_START,
            window_end=WINDOW_END,
        )


def test_capability_refuses_unstable_process() -> None:
    bundle = seeded_bundle(outlier=11.5)
    with pytest.raises(UnstableProcessError):
        generate_capability_report(
            bundle.services,
            actor=ACTOR,
            parameter_id=ParameterId("OXIDE_THK"),
            product_id=ProductId("DEV-A"),
            window_start=WINDOW_START,
            window_end=WINDOW_END,
        )
    refused = bundle.audit.list_for(AuditEventType.REPORT_REFUSED)
    assert len(refused) == 1
    assert refused[0].succeeded is False


def test_capability_succeeds_when_in_control() -> None:
    bundle = seeded_bundle()
    outcome = generate_capability_report(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        product_id=ProductId("DEV-A"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )
    assert outcome.refused is False
    assert outcome.result is not None
    assert outcome.result.within.cpk > 0
    assert bundle.audit.list_for(AuditEventType.REPORT_GENERATED)


def test_audit_write_failure_aborts_disposition() -> None:
    bundle = seeded_bundle(fail_audit=True)
    with pytest.raises(AuditWriteError):
        record_disposition(
            bundle.services,
            actor=ACTOR,
            lot_id=LotId("LOT-001"),
            action=DispositionAction.HOLD,
            reason="hold for investigation",
        )
    assert bundle.dispositions.list_for(LotId("LOT-001")) == ()


def test_unauthorised_disposition_is_refused() -> None:
    bundle = seeded_bundle()
    denied = FakeAuthorisation(denied=frozenset({(str(ACTOR), ProtectedAction.RECORD_DISPOSITION)}))
    services = ApplicationServices(
        clock=bundle.services.clock,
        audit=bundle.services.audit,
        auth=denied,
        measurements=bundle.services.measurements,
        baselines=bundle.services.baselines,
        violations=bundle.services.violations,
        dispositions=bundle.services.dispositions,
        specifications=bundle.services.specifications,
        excursions=bundle.services.excursions,
        control_plans=bundle.services.control_plans,
        report_renderer=bundle.services.report_renderer,
        notifier=bundle.services.notifier,
        rule_set=bundle.services.rule_set,
        code_revision=bundle.services.code_revision,
        config_revision=bundle.services.config_revision,
    )
    with pytest.raises(UnauthorisedActionError):
        record_disposition(
            services,
            actor=ACTOR,
            lot_id=LotId("LOT-001"),
            action=DispositionAction.SCRAP,
            reason="beyond salvage",
        )


def test_acknowledge_unknown_violation() -> None:
    bundle = seeded_bundle()
    with pytest.raises(InsufficientDataError):
        acknowledge_violation(
            bundle.services,
            actor=ACTOR,
            violation_id="vio-missing",
        )


def test_acknowledge_violation_happy_path() -> None:
    bundle = seeded_bundle(outlier=11.5)
    result = evaluate_lot(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        lot_id=LotId("LOT-001"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )
    violation_id = result.violations[0].violation_id
    updated = acknowledge_violation(
        bundle.services,
        actor=ACTOR,
        violation_id=violation_id,
        reason="reviewed",
    )
    assert updated.acknowledged is True
    assert bundle.audit.list_for(AuditEventType.VIOLATION_ACKNOWLEDGED)


def test_recompute_baseline_activates_and_audits() -> None:
    bundle = seeded_bundle()
    outcome = recompute_baseline(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        activate=True,
        reason="phase I qualification",
    )
    assert outcome.baseline.status.value == "active"
    assert outcome.previous_active_id is not None
    assert bundle.audit.list_for(AuditEventType.BASELINE_CREATED)
    assert bundle.audit.list_for(AuditEventType.BASELINE_APPROVED)
    assert bundle.audit.list_for(AuditEventType.BASELINE_SUPERSEDED)


def test_record_disposition_audits() -> None:
    bundle = seeded_bundle()
    disposition = record_disposition(
        bundle.services,
        actor=ACTOR,
        lot_id=LotId("LOT-001"),
        action=DispositionAction.CONTINUE,
        reason="false alarm after remeasure",
    )
    assert disposition.action is DispositionAction.CONTINUE
    assert bundle.audit.list_for(AuditEventType.VIOLATION_DISPOSITIONED)


def test_run_gauge_study() -> None:
    bundle = build_local_bundle()
    rng = np.random.default_rng(0)
    part = rng.normal(0.0, 2.0, size=10)
    data = np.zeros((10, 3, 3), dtype=np.float64)
    for p_index in range(10):
        for o_index in range(3):
            data[p_index, o_index, :] = part[p_index] + rng.normal(0.0, 0.2, size=3)
    outcome = run_gauge_study(
        bundle.services,
        actor=ACTOR,
        measurements=data,
        acceptable_percent=10.0,
        marginal_percent=30.0,
        minimum_distinct_categories=5,
        tolerance=10.0,
    )
    assert outcome.judgement.verdict.value in {
        "acceptable",
        "marginal",
        "unacceptable",
    }
    assert bundle.audit.list_for(AuditEventType.REPORT_GENERATED)


def test_get_wafer_map_audits_access() -> None:
    bundle = build_local_bundle()
    revision = DataRevision("rev-wafer")
    rows = [
        a_measurement(
            data_revision=revision,
            value=10.0 + 0.01 * index,
            timestamp=aware(month=7, day=2) + timedelta(minutes=index),
            site_id=SiteId(index + 1),
            site_x_mm=float(index),
            site_y_mm=0.0,
            lot_id=LotId("LOT-MAP"),
            wafer_id=WaferId("LOT-MAP:1"),
        )
        for index in range(5)
    ]
    bundle.measurements.replace_revision(revision, tuple(rows))
    view = get_wafer_map(
        bundle.services,
        actor=ACTOR,
        parameter_id=ParameterId("OXIDE_THK"),
        lot_id=LotId("LOT-MAP"),
        wafer_id=WaferId("LOT-MAP:1"),
    )
    assert view.n_sites_total == 5
    assert len(view.sites) == 5
    assert view.spatial_signature is None
    assert view.is_aggregated is False
    assert bundle.audit.list_for(AuditEventType.MEASUREMENT_DATA_ACCESS)
