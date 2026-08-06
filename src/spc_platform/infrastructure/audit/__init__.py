"""Audit trail adapters (append-only)."""

from spc_platform.infrastructure.audit.append_only_store import FileAuditStore
from spc_platform.infrastructure.audit.fake import FakeAuditSink

__all__ = ["FakeAuditSink", "FileAuditStore"]
