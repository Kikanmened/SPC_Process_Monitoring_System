"""Observability: structured logging, metrics, and — separately — the audit trail.

Operational logs help an engineer debug and may be rotated away; audit records
prove what the system did and who instructed it, are append-only, and their
loss is an audit finding. Same mechanism, incompatible requirements, separate
sinks (SYSTEM_ARCHITECTURE.md §3.6).
"""
