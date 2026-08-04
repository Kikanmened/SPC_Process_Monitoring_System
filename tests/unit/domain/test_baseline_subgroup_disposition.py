"""Baseline, subgrouping, violation, and disposition invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tests.factories.domain import a_baseline, a_control_limit, aware

from spc_platform.domain import (
    ActorId,
    Disposition,
    DispositionAction,
    DomainInvariantError,
    LotId,
    OcapId,
    ParameterId,
    Subgroup,
    SubgroupingKind,
    SubgroupingStrategy,
    Violation,
)
from spc_platform.domain.enums import ChartType, ViolationSeverity
from spc_platform.domain.ids import BaselineId, RuleId


@pytest.mark.unit
def test_active_baseline_requires_approver() -> None:
    with pytest.raises((ValidationError, DomainInvariantError)):
        a_baseline(approved_by=None, approved_at=None)


@pytest.mark.unit
def test_baseline_window_must_be_ordered() -> None:
    with pytest.raises((ValidationError, DomainInvariantError)):
        a_baseline(window_start=aware(day=10), window_end=aware(day=1))


@pytest.mark.unit
def test_baseline_limits_must_share_parameter_and_id() -> None:
    limits = a_control_limit(parameter_id=ParameterId("OTHER"))
    with pytest.raises((ValidationError, DomainInvariantError)):
        a_baseline(limits=limits)


@pytest.mark.unit
def test_sites_as_subgroup_requires_explicit_declaration() -> None:
    with pytest.raises((ValidationError, DomainInvariantError)):
        SubgroupingStrategy(
            kind=SubgroupingKind.SITES_AS_SUBGROUP,
            explicitly_declared=False,
        )


@pytest.mark.unit
def test_sites_as_subgroup_allowed_when_explicit() -> None:
    strategy = SubgroupingStrategy(
        kind=SubgroupingKind.SITES_AS_SUBGROUP,
        explicitly_declared=True,
    )
    assert strategy.kind is SubgroupingKind.SITES_AS_SUBGROUP


@pytest.mark.unit
def test_subgroup_records_strategy() -> None:
    subgroup = Subgroup(
        parameter_id=ParameterId("OXIDE_THK"),
        strategy=SubgroupingStrategy(kind=SubgroupingKind.WAFER_MEAN),
        values=(10.0, 10.1, 9.9),
        timestamp=aware(),
    )
    assert subgroup.strategy.kind is SubgroupingKind.WAFER_MEAN


@pytest.mark.unit
def test_disposition_requires_non_blank_reason() -> None:
    with pytest.raises(ValidationError):
        Disposition(
            lot_id=LotId("LOT-1"),
            action=DispositionAction.HOLD,
            actor=ActorId("shift.lead"),
            timestamp=aware(),
            reason="   ",
            ocap_id=OcapId("OCAP-1"),
        )


@pytest.mark.unit
def test_violation_records_rule_chart_and_point() -> None:
    violation = Violation(
        parameter_id=ParameterId("OXIDE_THK"),
        baseline_id=BaselineId("BL-1"),
        rule_id=RuleId("WE1"),
        chart_type=ChartType.I_MR,
        severity=ViolationSeverity.CRITICAL,
        point_index=12,
        timestamp=aware(),
        statistic_value=10.4,
    )
    assert violation.rule_id == RuleId("WE1")
    assert violation.point_index == 12
