"""Validate API responses against the generated OpenAPI schema."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from tests.factories.application import WINDOW_END, WINDOW_START, seeded_bundle

from spc_platform.api.app import create_app


def _schema_for(openapi: dict[str, Any], model_name: str) -> dict[str, Any]:
    schemas = openapi["components"]["schemas"]
    schema = dict(schemas[model_name])
    schema["$defs"] = schemas
    return schema


def _validate(openapi: dict[str, Any], model_name: str, payload: object) -> None:
    schema = _schema_for(openapi, model_name)
    Draft202012Validator(schema).validate(payload)


@pytest.fixture
def app() -> FastAPI:
    bundle = seeded_bundle()
    application = create_app(bundle.services)
    application.state.bundle = bundle
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.mark.contract
def test_evaluate_lot_matches_openapi(app: FastAPI, client: TestClient) -> None:
    openapi = app.openapi()
    response = client.post(
        "/v1/lots/evaluate",
        headers={"X-Actor-Id": "qe.smith"},
        json={
            "parameter_id": "OXIDE_THK",
            "lot_id": "LOT-001",
            "window_start": WINDOW_START.isoformat(),
            "window_end": WINDOW_END.isoformat(),
        },
    )
    assert response.status_code == 200
    _validate(openapi, "EvaluateLotResponse", response.json())


@pytest.mark.contract
def test_capability_refusal_error_shape() -> None:
    bundle = seeded_bundle(outlier=11.5)
    unstable = TestClient(create_app(bundle.services))
    response = unstable.post(
        "/v1/reports/capability",
        headers={"X-Actor-Id": "qe.smith"},
        json={
            "parameter_id": "OXIDE_THK",
            "product_id": "DEV-A",
            "window_start": WINDOW_START.isoformat(),
            "window_end": WINDOW_END.isoformat(),
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body["error"] == "UnstableProcessError"
    assert "message" in body


@pytest.mark.contract
def test_disposition_matches_openapi(app: FastAPI, client: TestClient) -> None:
    openapi = app.openapi()
    response = client.post(
        "/v1/dispositions",
        headers={"X-Actor-Id": "qe.smith"},
        json={
            "lot_id": "LOT-001",
            "action": "hold",
            "reason": "awaiting metrology review",
        },
    )
    assert response.status_code == 200
    _validate(openapi, "RecordDispositionResponse", response.json())


@pytest.mark.contract
def test_openapi_declares_seven_use_case_paths(app: FastAPI) -> None:
    paths = set(app.openapi()["paths"])
    expected = {
        "/v1/lots/evaluate",
        "/v1/baselines/recompute",
        "/v1/violations/acknowledge",
        "/v1/dispositions",
        "/v1/reports/capability",
        "/v1/msa/gauge-study",
        "/v1/wafers/map",
    }
    assert expected <= paths
