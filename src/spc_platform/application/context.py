"""Shared collaborators injected into every use case."""

from __future__ import annotations

from dataclasses import dataclass

from spc_platform.application.ports.audit_sink import AuditSink
from spc_platform.application.ports.authorisation import Authorisation
from spc_platform.application.ports.baseline_store import BaselineStore
from spc_platform.application.ports.disposition_repository import DispositionRepository
from spc_platform.application.ports.measurement_repository import MeasurementRepository
from spc_platform.application.ports.specification_repository import SpecificationRepository
from spc_platform.application.ports.violation_repository import ViolationRepository
from spc_platform.common.time import Clock
from spc_platform.domain.chart_spec import RuleSet
from spc_platform.domain.ids import CodeRevision, ConfigRevision


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    """Ports and policies shared across use cases."""

    clock: Clock
    audit: AuditSink
    auth: Authorisation
    measurements: MeasurementRepository
    baselines: BaselineStore
    violations: ViolationRepository
    dispositions: DispositionRepository
    specifications: SpecificationRepository
    rule_set: RuleSet
    code_revision: CodeRevision
    config_revision: ConfigRevision
