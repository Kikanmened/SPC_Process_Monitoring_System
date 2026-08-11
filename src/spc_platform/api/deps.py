"""FastAPI dependency injection for use-case services."""

from __future__ import annotations

import os
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


def get_actor(
    x_actor_id: Annotated[str | None, Header(alias="X-Actor-Id")] = None,
    x_forwarded_user: Annotated[str | None, Header(alias="X-Forwarded-User")] = None,
) -> ActorId:
    """Resolve actor from local header or trusted reverse-proxy SSO headers.

    ``SPC_AUTH_MODE=header`` (default/local): require ``X-Actor-Id``.
    ``SPC_AUTH_MODE=proxy`` (staging/production behind site SSO): accept
    ``X-Forwarded-User`` set by the site reverse proxy after SSO/LDAP
    (FR-CF05, DEPLOYMENT_PLAN.md §10).
    """
    mode = os.environ.get("SPC_AUTH_MODE", "header").strip().lower()
    if mode == "proxy":
        candidate = (x_forwarded_user or x_actor_id or "").strip()
        if not candidate:
            message = "proxy auth requires X-Forwarded-User (or X-Actor-Id fallback)"
            raise ValueError(message)
        return ActorId(candidate)
    candidate = (x_actor_id or "").strip()
    if not candidate:
        message = "X-Actor-Id header must identify the actor"
        raise ValueError(message)
    return ActorId(candidate)


ServicesDep = Annotated[ApplicationServices, Depends(get_services)]
ActorDep = Annotated[ActorId, Depends(get_actor)]
