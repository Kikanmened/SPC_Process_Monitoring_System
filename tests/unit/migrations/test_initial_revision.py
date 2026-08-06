"""The initial Alembic revision embeds the shared DDL."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from spc_platform.infrastructure.repositories import ddl


@pytest.mark.unit
def test_initial_revision_defines_upgrade_and_downgrade() -> None:
    path = (
        Path(__file__).resolve().parents[3]
        / "migrations"
        / "versions"
        / "20260806_0001_initial_schema.py"
    )
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "upgrade" in names
    assert "downgrade" in names
    assert "CREATE TABLE IF NOT EXISTS measurements" in ddl.MEASUREMENTS_DDL
    assert "CREATE TABLE IF NOT EXISTS baselines" in ddl.BASELINES_DDL
