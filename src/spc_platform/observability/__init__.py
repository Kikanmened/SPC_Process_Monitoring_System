"""Observability: structured logging, metrics, and — separately — the audit trail.

Operational logs help an engineer debug and may be rotated away; audit records
prove what the system did and who instructed it, are append-only, and their
loss is an audit finding. Same mechanism, incompatible requirements, separate
sinks (SYSTEM_ARCHITECTURE.md §3.6).
"""

from spc_platform.observability.logging import configure_logging, get_logger
from spc_platform.observability.metrics import METRICS, MetricsRegistry

__all__ = [
    "METRICS",
    "MetricsRegistry",
    "configure_logging",
    "get_logger",
]
