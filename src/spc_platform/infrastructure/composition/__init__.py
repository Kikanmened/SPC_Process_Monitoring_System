"""Composition helpers that wire adapters for local API and CLI roots."""

from spc_platform.infrastructure.composition.local_services import (
    LocalBundle,
    build_local_bundle,
)

__all__ = ["LocalBundle", "build_local_bundle"]
