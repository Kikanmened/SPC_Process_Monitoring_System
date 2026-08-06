"""FastAPI dependency injection for use-case services."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request

from spc_platform.application.context import ApplicationServices
from spc_platform.domain.ids import ActorId


def get_services(request: Request) -> ApplicationServices:
    """Return the ``ApplicationServices`` bound on the app state."""
    services = getattr(request.app.state, "services", None)
    if services is None:
        message = "application services are not configured on the FastAPI app"
        raise RuntimeError(message)
    if not isinstance(services, ApplicationServices):
        message = "app.state.services must be ApplicationServices"
        raise TypeError(message)
    return services


def get_actor(x_actor_id: Annotated[str, Header(alias="X-Actor-Id")]) -> ActorId:
    """Resolve the acting identity from the local/dev header (no SSO in Phase 11)."""
    if not x_actor_id.strip():
        message = "X-Actor-Id header must identify the actor"
        raise ValueError(message)
    return ActorId(x_actor_id.strip())


ServicesDep = Annotated[ApplicationServices, Depends(get_services)]
ActorDep = Annotated[ActorId, Depends(get_actor)]
