"""Append-only audit records for consequential actions (FR-AU01 - FR-AU03).

Event types match QUALITY_ASSURANCE_PLAN.md §2.2. Records are written through
the ``AuditSink`` port; adapters must never rewrite prior lines.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from spc_platform.common.provenance import Provenance
from spc_platform.common.time import require_aware
from spc_platform.domain.ids import ActorId


class AuditEventType(StrEnum):
    """Minimum auditable event set from QUALITY_ASSURANCE_PLAN.md §2.2."""

    CONTROL_LIMIT_CHANGE = "control_limit_change"
    BASELINE_CREATED = "baseline_created"
    BASELINE_APPROVED = "baseline_approved"
    BASELINE_SUPERSEDED = "baseline_superseded"
    SPECIFICATION_LIMIT_CHANGE = "specification_limit_change"
    VIOLATION_RAISED = "violation_raised"
    VIOLATION_ACKNOWLEDGED = "violation_acknowledged"
    VIOLATION_DISPOSITIONED = "violation_dispositioned"
    RULE_SET_CHANGE = "rule_set_change"
    CHART_TYPE_CHANGE = "chart_type_change"
    REPORT_GENERATED = "report_generated"
    REPORT_REFUSED = "report_refused"
    PIPELINE_RUN = "pipeline_run"
    MEASUREMENT_DATA_ACCESS = "measurement_data_access"
    EXCURSION_OPENED = "excursion_opened"
    EXCURSION_CONTAINED = "excursion_contained"
    EXCURSION_INVESTIGATING = "excursion_investigating"
    EXCURSION_DISPOSITIONED = "excursion_dispositioned"
    EXCURSION_CLOSED = "excursion_closed"
    NOTIFICATION_DISPATCHED = "notification_dispatched"
    AUDIT_PACKAGE_ASSEMBLED = "audit_package_assembled"


class AuditRecord(BaseModel):
    """One append-only audit entry (ALCOA+: attributable, contemporaneous)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_id: str = Field(min_length=1)
    event_type: AuditEventType
    actor: ActorId
    timestamp: datetime
    reason: str = ""
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    provenance: Provenance | None = None
    succeeded: bool = True

    @field_validator("timestamp")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return require_aware(value, field_name="timestamp")


def new_audit_record(  # noqa: PLR0913 — audit record fields are intentional
    *,
    event_type: AuditEventType,
    actor: ActorId,
    timestamp: datetime,
    reason: str = "",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    provenance: Provenance | None = None,
    succeeded: bool = True,
) -> AuditRecord:
    """Build a record with a unique identity."""
    return AuditRecord(
        record_id=f"aud-{uuid4().hex}",
        event_type=event_type,
        actor=actor,
        timestamp=timestamp,
        reason=reason,
        before=before or {},
        after=after or {},
        provenance=provenance,
        succeeded=succeeded,
    )
