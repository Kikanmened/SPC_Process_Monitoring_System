"""Wire in-memory adapters into ``ApplicationServices`` for local runs and tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from spc_platform.application.context import ApplicationServices
from spc_platform.common.time import Clock, SystemClock
from spc_platform.domain.chart_spec import RuleDefinition, RuleSet
from spc_platform.domain.enums import ViolationSeverity
from spc_platform.domain.ids import (
    CodeRevision,
    ConfigRevision,
    OcapId,
    ParameterId,
    ProductId,
    RuleId,
)
from spc_platform.infrastructure.audit.fake import FakeAuditSink
from spc_platform.infrastructure.notifications.recording_notifier import RecordingNotifier
from spc_platform.infrastructure.reporting.html_renderer import JinjaReportRenderer
from spc_platform.infrastructure.repositories.fake import (
    FakeBaselineStore,
    FakeMeasurementRepository,
)
from spc_platform.infrastructure.repositories.support_fakes import (
    AllowAllAuthorisation,
    FakeControlPlanLookup,
    FakeDispositionRepository,
    FakeExcursionRepository,
    FakeSpecificationRepository,
    FakeViolationRepository,
)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_NOTIFICATIONS_PATH = _REPO_ROOT / "configs" / "alerting" / "notifications.yaml"
_CONTROL_PLANS_PATH = _REPO_ROOT / "data" / "reference" / "control_plans.yaml"


def western_electric_rule_set() -> RuleSet:
    """WE-1 only — enough for Phase II Shewhart signalling in local demos."""
    return RuleSet(
        name="western_electric_1",
        rules=(
            RuleDefinition(
                rule_id=RuleId("WE-1"),
                severity=ViolationSeverity.CRITICAL,
            ),
        ),
    )


def _load_notification_policy() -> tuple[int, int, str]:
    if not _NOTIFICATIONS_PATH.is_file():
        return 900, 3600, "shift.lead@local"
    payload = yaml.safe_load(_NOTIFICATIONS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return 900, 3600, "shift.lead@local"
    digest = int(payload.get("digest_interval_seconds", 900))
    escalate = int(payload.get("escalate_unacknowledged_after_seconds", 3600))
    recipient = str(payload.get("default_recipient", "shift.lead@local"))
    return digest, escalate, recipient


def _load_control_plan_lookup() -> FakeControlPlanLookup:
    lookup = FakeControlPlanLookup()
    if not _CONTROL_PLANS_PATH.is_file():
        return lookup
    payload = yaml.safe_load(_CONTROL_PLANS_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return lookup
    plans = payload.get("control_plans", [])
    if not isinstance(plans, list):
        return lookup
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        characteristics = plan.get("characteristics", [])
        if not isinstance(characteristics, list):
            continue
        for row in characteristics:
            if not isinstance(row, dict):
                continue
            parameter_id = row.get("parameter_id")
            ocap_id = row.get("ocap_id")
            product_id = row.get("product_id")
            if parameter_id is None or ocap_id is None:
                continue
            lookup.seed(
                ParameterId(str(parameter_id)),
                OcapId(str(ocap_id)),
                ProductId(str(product_id)) if product_id is not None else None,
            )
            # Also seed parameter-only so alarm queue without product still resolves.
            lookup.seed(ParameterId(str(parameter_id)), OcapId(str(ocap_id)))
    return lookup


@dataclass(slots=True)
class LocalBundle:
    """Concrete adapters plus the services object use cases consume."""

    services: ApplicationServices
    measurements: FakeMeasurementRepository
    baselines: FakeBaselineStore
    violations: FakeViolationRepository
    dispositions: FakeDispositionRepository
    specifications: FakeSpecificationRepository
    excursions: FakeExcursionRepository
    control_plans: FakeControlPlanLookup
    audit: FakeAuditSink
    notifier: RecordingNotifier


def build_local_bundle(
    *,
    clock: Clock | None = None,
    code_revision: CodeRevision | None = None,
    config_revision: ConfigRevision | None = None,
    rule_set: RuleSet | None = None,
    fail_audit_writes: bool = False,
) -> LocalBundle:
    """Build a fully wired local stack with fake adapters."""
    resolved_clock = clock if clock is not None else SystemClock()
    measurements = FakeMeasurementRepository()
    baselines = FakeBaselineStore()
    violations = FakeViolationRepository()
    dispositions = FakeDispositionRepository()
    specifications = FakeSpecificationRepository()
    excursions = FakeExcursionRepository()
    control_plans = _load_control_plan_lookup()
    audit = FakeAuditSink(fail_writes=fail_audit_writes)
    notifier = RecordingNotifier(resolved_clock)
    digest, escalate, recipient = _load_notification_policy()
    services = ApplicationServices(
        clock=resolved_clock,
        audit=audit,
        auth=AllowAllAuthorisation(),
        measurements=measurements,
        baselines=baselines,
        violations=violations,
        dispositions=dispositions,
        specifications=specifications,
        excursions=excursions,
        control_plans=control_plans,
        report_renderer=JinjaReportRenderer(),
        notifier=notifier,
        rule_set=rule_set if rule_set is not None else western_electric_rule_set(),
        code_revision=code_revision or CodeRevision("local-dev"),
        config_revision=config_revision or ConfigRevision("local-dev"),
        notification_digest_seconds=digest,
        notification_escalate_seconds=escalate,
        notification_recipient=recipient,
    )
    return LocalBundle(
        services=services,
        measurements=measurements,
        baselines=baselines,
        violations=violations,
        dispositions=dispositions,
        specifications=specifications,
        excursions=excursions,
        control_plans=control_plans,
        audit=audit,
        notifier=notifier,
    )
