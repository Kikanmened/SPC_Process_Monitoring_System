"""Wire in-memory adapters into ``ApplicationServices`` for local runs and tests."""

from __future__ import annotations

from dataclasses import dataclass

from spc_platform.application.context import ApplicationServices
from spc_platform.common.time import Clock, SystemClock
from spc_platform.domain.chart_spec import RuleDefinition, RuleSet
from spc_platform.domain.enums import ViolationSeverity
from spc_platform.domain.ids import CodeRevision, ConfigRevision, RuleId
from spc_platform.infrastructure.audit.fake import FakeAuditSink
from spc_platform.infrastructure.repositories.fake import (
    FakeBaselineStore,
    FakeMeasurementRepository,
)
from spc_platform.infrastructure.repositories.support_fakes import (
    AllowAllAuthorisation,
    FakeDispositionRepository,
    FakeSpecificationRepository,
    FakeViolationRepository,
)


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


@dataclass(slots=True)
class LocalBundle:
    """Concrete adapters plus the services object use cases consume."""

    services: ApplicationServices
    measurements: FakeMeasurementRepository
    baselines: FakeBaselineStore
    violations: FakeViolationRepository
    dispositions: FakeDispositionRepository
    specifications: FakeSpecificationRepository
    audit: FakeAuditSink


def build_local_bundle(
    *,
    clock: Clock | None = None,
    code_revision: CodeRevision | None = None,
    config_revision: ConfigRevision | None = None,
    rule_set: RuleSet | None = None,
    fail_audit_writes: bool = False,
) -> LocalBundle:
    """Build a fully wired local stack with fake adapters."""
    measurements = FakeMeasurementRepository()
    baselines = FakeBaselineStore()
    violations = FakeViolationRepository()
    dispositions = FakeDispositionRepository()
    specifications = FakeSpecificationRepository()
    audit = FakeAuditSink(fail_writes=fail_audit_writes)
    services = ApplicationServices(
        clock=clock if clock is not None else SystemClock(),
        audit=audit,
        auth=AllowAllAuthorisation(),
        measurements=measurements,
        baselines=baselines,
        violations=violations,
        dispositions=dispositions,
        specifications=specifications,
        rule_set=rule_set if rule_set is not None else western_electric_rule_set(),
        code_revision=code_revision or CodeRevision("local-dev"),
        config_revision=config_revision or ConfigRevision("local-dev"),
    )
    return LocalBundle(
        services=services,
        measurements=measurements,
        baselines=baselines,
        violations=violations,
        dispositions=dispositions,
        specifications=specifications,
        audit=audit,
    )
