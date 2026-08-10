"""Dispatch digested notifications for open violations (FR-A05, FR-A06)."""

from __future__ import annotations

from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.ports.notifier import (
    DigestItem,
    DispatchReceipt,
    NotificationDigest,
)
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.common.errors import InsufficientDataError
from spc_platform.domain.ids import ActorId, ParameterId, ProductId


def dispatch_notifications(
    services: ApplicationServices,
    *,
    actor: ActorId,
    parameter_id: ParameterId | None = None,
    product_id: ProductId | None = None,
) -> DispatchReceipt:
    """Group open violations into one digest for the configured recipient.

    Escalation is marked on items older than ``notification_escalate_seconds``
    without acknowledgement (FR-A06). Never emits one message per violation.
    """
    services.auth.require(actor, ProtectedAction.DISPATCH_NOTIFICATIONS)
    open_items = services.violations.list_open(parameter_id)
    if not open_items:
        raise InsufficientDataError("no open violations to digest")
    now = services.clock.now()
    digest_items: list[DigestItem] = []
    for item in open_items:
        age = (now - item.violation.timestamp).total_seconds()
        escalated = (not item.acknowledged) and age >= services.notification_escalate_seconds
        ocap = services.control_plans.ocap_for(item.violation.parameter_id, product_id)
        digest_items.append(
            DigestItem(
                violation_id=item.violation_id,
                parameter_id=str(item.violation.parameter_id),
                severity=item.violation.severity.value,
                timestamp=item.violation.timestamp,
                ocap_id=None if ocap is None else str(ocap),
                escalated=escalated,
            )
        )
    digest_items.sort(key=lambda row: (row.severity, row.timestamp.isoformat(), row.violation_id))
    digest = NotificationDigest(
        recipient=services.notification_recipient,
        interval_seconds=services.notification_digest_seconds,
        items=tuple(digest_items),
        generated_at=now,
    )
    receipt = services.notifier.dispatch(digest)
    write_audit(
        services,
        event_type=AuditEventType.NOTIFICATION_DISPATCHED,
        actor=actor,
        reason="digested notification",
        after={
            "recipient": receipt.recipient,
            "item_count": receipt.item_count,
            "digest_id": receipt.digest_id,
            "escalated_count": sum(1 for item in digest_items if item.escalated),
        },
    )
    return receipt
