"""Liveness, readiness, and metrics endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient
from tests.factories.application import seeded_bundle

from spc_platform.api.app import create_app


def test_health_ready_metrics() -> None:
    bundle = seeded_bundle()
    client = TestClient(create_app(bundle.services))
    assert client.get("/health").json() == {"status": "ok"}
    ready = client.get("/ready").json()
    assert ready["status"] == "ready"
    assert ready["checks"]["clock"] is True
    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert "text/plain" in metrics.headers["content-type"]
