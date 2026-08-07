"""Cache helpers that bind views to data and configuration revisions (NFR-U06)."""

from __future__ import annotations

from spc_platform.application.context import ApplicationServices
from spc_platform.domain.ids import DataRevision
from spc_platform.infrastructure.composition import LocalBundle


def cache_key(
    data_revision: DataRevision | str,
    config_revision: str,
    *parts: object,
) -> tuple[object, ...]:
    """Build a cache key that invalidates when data or config changes."""
    return (str(data_revision), str(config_revision), *parts)


def get_services(bundle: LocalBundle) -> ApplicationServices:
    """Return the use-case collaborator object from a composition bundle."""
    return bundle.services
