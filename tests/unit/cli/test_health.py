"""CLI health probe used by container HEALTHCHECK."""

from __future__ import annotations

from tests.factories.application import seeded_bundle
from typer.testing import CliRunner

from spc_platform.cli.app import create_cli


def test_cli_health_ok() -> None:
    runner = CliRunner()
    result = runner.invoke(create_cli(seeded_bundle()), ["health"])
    assert result.exit_code == 0
    assert '"status": "ok"' in result.stdout
