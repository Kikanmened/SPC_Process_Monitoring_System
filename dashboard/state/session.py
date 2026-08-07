"""Streamlit session bootstrap for the local fake / DuckDB composition root."""

from __future__ import annotations

from spc_platform.domain.ids import ActorId
from spc_platform.infrastructure.composition import LocalBundle, build_local_bundle


def default_actor() -> ActorId:
    """Local/dev actor until site SSO arrives in Phase 14."""
    return ActorId("dashboard.operator")


def ensure_bundle(session_state: dict[str, object]) -> LocalBundle:
    """Create or reuse the composition root in Streamlit session state."""
    existing = session_state.get("spc_bundle")
    if isinstance(existing, LocalBundle):
        return existing
    bundle = build_local_bundle()
    session_state["spc_bundle"] = bundle
    return bundle
