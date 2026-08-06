"""Shared DDL for measurement and baseline tables (DuckDB and PostgreSQL)."""

from __future__ import annotations

MEASUREMENTS_DDL = """
CREATE TABLE IF NOT EXISTS measurements (
    measurement_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    lot_id TEXT NOT NULL,
    wafer_id TEXT NOT NULL,
    slot INTEGER NOT NULL,
    site_id INTEGER NOT NULL,
    site_x_mm DOUBLE PRECISION NOT NULL,
    site_y_mm DOUBLE PRECISION NOT NULL,
    parameter_id TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT NOT NULL,
    step_id TEXT NOT NULL,
    tool_id TEXT NOT NULL,
    chamber_id TEXT NOT NULL,
    recipe_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    metrology_tool_id TEXT NOT NULL,
    measurement_status TEXT NOT NULL,
    data_revision TEXT NOT NULL
)
"""

MEASUREMENTS_INDEXES = (
    """
    CREATE INDEX IF NOT EXISTS ix_measurements_series
    ON measurements (parameter_id, timestamp, data_revision)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_measurements_wafer
    ON measurements (parameter_id, lot_id, wafer_id, data_revision)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_measurements_revision
    ON measurements (data_revision)
    """,
)

BASELINES_DDL = """
CREATE TABLE IF NOT EXISTS baselines (
    baseline_id TEXT PRIMARY KEY,
    parameter_id TEXT NOT NULL,
    status TEXT NOT NULL,
    n_observations INTEGER NOT NULL,
    sigma_estimator TEXT NOT NULL,
    centre_line DOUBLE PRECISION NOT NULL,
    lcl DOUBLE PRECISION NOT NULL,
    ucl DOUBLE PRECISION NOT NULL,
    sigma_estimate DOUBLE PRECISION NOT NULL,
    sigma_multiplier DOUBLE PRECISION NOT NULL,
    limits_unit TEXT NOT NULL,
    window_start TIMESTAMP NOT NULL,
    window_end TIMESTAMP NOT NULL,
    approved_by TEXT,
    approved_at TIMESTAMP,
    supersedes TEXT,
    effective_from TIMESTAMP NOT NULL
)
"""

BASELINES_INDEXES = (
    """
    CREATE INDEX IF NOT EXISTS ix_baselines_parameter_status
    ON baselines (parameter_id, status, effective_from)
    """,
)
