"""API and CLI share the evaluate_lot use case against the same fake stack."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient
from tests.factories.application import WINDOW_END, WINDOW_START, seeded_bundle
from typer.testing import CliRunner

from spc_platform.api.app import create_app
from spc_platform.application.use_cases import evaluate_lot
from spc_platform.cli.app import create_cli
from spc_platform.domain.ids import ActorId, LotId, ParameterId


def test_api_and_cli_evaluate_lot_agree() -> None:
    bundle = seeded_bundle(outlier=11.5)
    actor = ActorId("qe.smith")
    direct = evaluate_lot(
        bundle.services,
        actor=actor,
        parameter_id=ParameterId("OXIDE_THK"),
        lot_id=LotId("LOT-001"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
    )

    # Fresh identical stack for API (same seed path).
    api_bundle = seeded_bundle(outlier=11.5)
    client = TestClient(create_app(api_bundle.services))
    api_response = client.post(
        "/v1/lots/evaluate",
        headers={"X-Actor-Id": "qe.smith"},
        json={
            "parameter_id": "OXIDE_THK",
            "lot_id": "LOT-001",
            "window_start": WINDOW_START.isoformat(),
            "window_end": WINDOW_END.isoformat(),
        },
    )
    assert api_response.status_code == 200
    api_body = api_response.json()
    assert api_body["points_evaluated"] == direct.points_evaluated
    assert len(api_body["violation_ids"]) == len(direct.violations)

    cli_bundle = seeded_bundle(outlier=11.5)
    runner = CliRunner()
    result = runner.invoke(
        create_cli(cli_bundle),
        [
            "--actor",
            "qe.smith",
            "evaluate-lot",
            "--parameter-id",
            "OXIDE_THK",
            "--lot-id",
            "LOT-001",
            "--window-start",
            WINDOW_START.isoformat(),
            "--window-end",
            WINDOW_END.isoformat(),
        ],
    )
    assert result.exit_code == 0, result.output
    cli_body = json.loads(result.output)
    assert cli_body["points_evaluated"] == direct.points_evaluated
    assert len(cli_body["violation_ids"]) == len(direct.violations)


def test_api_capability_refusal_e2e() -> None:
    bundle = seeded_bundle(outlier=11.5)
    client = TestClient(create_app(bundle.services))
    response = client.post(
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
    assert response.json()["error"] == "UnstableProcessError"
