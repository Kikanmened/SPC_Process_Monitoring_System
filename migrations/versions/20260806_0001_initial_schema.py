"""Initial measurements and baselines schema.

Revision ID: 20260806_0001
Revises:
Create Date: 2026-08-06

The DDL matches ``spc_platform.infrastructure.repositories.ddl`` so DuckDB
local stores and PostgreSQL production stay aligned (ADR-0008).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

from spc_platform.infrastructure.repositories.ddl import (
    BASELINES_DDL,
    BASELINES_INDEXES,
    MEASUREMENTS_DDL,
    MEASUREMENTS_INDEXES,
)

revision: str = "20260806_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create measurement and baseline tables with indexes."""
    op.execute(MEASUREMENTS_DDL)
    for statement in MEASUREMENTS_INDEXES:
        op.execute(statement)
    op.execute(BASELINES_DDL)
    for statement in BASELINES_INDEXES:
        op.execute(statement)


def downgrade() -> None:
    """Drop measurement and baseline tables."""
    op.execute("DROP TABLE IF EXISTS baselines")
    op.execute("DROP TABLE IF EXISTS measurements")
