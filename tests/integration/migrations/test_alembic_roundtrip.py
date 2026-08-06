"""Alembic upgrade and downgrade against PostgreSQL when a URL is configured."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


@pytest.mark.integration
def test_alembic_upgrade_and_downgrade() -> None:
    url = os.environ.get("SPC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("SPC_TEST_DATABASE_URL not set")

    root = Path(__file__).resolve().parents[3]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    os.environ["SPC_TEST_DATABASE_URL"] = url

    command.upgrade(config, "head")
    engine = create_engine(url, future=True)
    with engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        }
    assert "measurements" in tables
    assert "baselines" in tables

    command.downgrade(config, "base")
    with engine.connect() as connection:
        tables_after = {
            row[0]
            for row in connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        }
    assert "measurements" not in tables_after
    assert "baselines" not in tables_after
