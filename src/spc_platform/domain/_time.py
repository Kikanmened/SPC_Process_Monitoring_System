"""Timezone awareness check local to domain.

``domain/`` cannot import ``common/``, so the boundary rule is duplicated here
with stdlib only. The application-facing helper lives in ``common.time``.
"""

from __future__ import annotations

from datetime import datetime

from spc_platform.domain.errors import DomainInvariantError


def require_aware(value: datetime, *, field_name: str) -> datetime:
    """Return ``value`` if timezone-aware; raise otherwise."""
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        raise DomainInvariantError(
            f"{field_name} must be timezone-aware",
            field_name=field_name,
        )
    return value
