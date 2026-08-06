"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from spc_platform.api.errors import register_exception_handlers
from spc_platform.api.routes import router
from spc_platform.application.context import ApplicationServices
from spc_platform.infrastructure.composition import build_local_bundle


def create_app(services: ApplicationServices | None = None) -> FastAPI:
    """Build the API app, wiring local fakes when services are not supplied."""
    app = FastAPI(
        title="SPC Platform API",
        version="0.11.0",
        description=(
            "Application use cases for semiconductor SPC. "
            "Actor identity via X-Actor-Id (SSO deferred to Phase 14)."
        ),
    )
    if services is None:
        bundle = build_local_bundle()
        services = bundle.services
        app.state.bundle = bundle
    app.state.services = services
    register_exception_handlers(app)
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        """Liveness probe for local runs."""
        return {"status": "ok"}

    return app
