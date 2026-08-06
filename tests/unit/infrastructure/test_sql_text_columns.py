"""SQL templates stay aligned with the row_mapping column tuples."""

from __future__ import annotations

import pytest

from spc_platform.infrastructure.repositories import sql_text
from spc_platform.infrastructure.repositories.row_mapping import (
    BASELINE_COLUMNS,
    MEASUREMENT_COLUMNS,
)


@pytest.mark.unit
def test_measurement_sql_lists_every_mapped_column() -> None:
    for column in MEASUREMENT_COLUMNS:
        assert column in sql_text.DUCKDB_SELECT_MEASUREMENTS
        assert column in sql_text.PG_SELECT_MEASUREMENTS
        assert f":{column}" in sql_text.PG_INSERT_MEASUREMENT


@pytest.mark.unit
def test_baseline_sql_lists_every_mapped_column() -> None:
    for column in BASELINE_COLUMNS:
        assert column in sql_text.DUCKDB_SELECT_BASELINE_BY_ID
        assert column in sql_text.PG_SELECT_BASELINE_BY_ID
        assert f":{column}" in sql_text.PG_INSERT_BASELINE
