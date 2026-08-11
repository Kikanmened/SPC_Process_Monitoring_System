"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, Response

from spc_platform.api.errors import register_exception_handlers
from spc_platform.api.routes import router
from spc_platform.application.context import ApplicationServices
from spc_platform.infrastructure.composition import build_local_bundle
from spc_platform.observability.logging import configure_logging
from spc_platform.observability.metrics import METRICS


def create_app(services: ApplicationServices | None = None) -> FastAPI:
    """Build the API app, wiring local fakes when services are not supplied."""
    configure_logging(json_logs=True)
    app = FastAPI(
        title="SPC Platform API",
        version="0.14.0",
        description=(
            "Application use cases for semiconductor SPC. "
            "Actor via X-Actor-Id (local) or X-Forwarded-User (SSO proxy mode)."
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
        """Liveness probe — process is up."""
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, object]:
        """Readiness probe — collaborators required for traffic are usable."""
        checks: dict[str, bool] = {
            "services": True,
            "clock": services.clock.now().tzinfo is not None,
            "audit": hasattr(services.audit, "append"),
        }
        status = "ready" if all(checks.values()) else "not_ready"
        return {"status": status, "checks": checks}

    @app.get("/metrics")
    def metrics() -> Response:
        """Prometheus text exposition for site collectors."""
        body = METRICS.render_prometheus()
        return Response(content=body, media_type="text/plain; version=0.0.4; charset=utf-8")

    return app
