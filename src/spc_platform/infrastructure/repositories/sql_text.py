"""SQL statement templates for measurement and baseline repositories.

Column lists are plain string literals kept in lockstep with
``row_mapping.MEASUREMENT_COLUMNS`` / ``BASELINE_COLUMNS`` by unit test.
Values are always bound parameters — never interpolated into these strings.
"""

from __future__ import annotations

# Measurement column order matches ``MEASUREMENT_COLUMNS`` in row_mapping.py.
DUCKDB_INSERT_MEASUREMENT = (
    "INSERT INTO measurements ("
    "measurement_id, timestamp, lot_id, wafer_id, slot, site_id, "
    "site_x_mm, site_y_mm, parameter_id, value, unit, step_id, tool_id, "
    "chamber_id, recipe_id, product_id, metrology_tool_id, "
    "measurement_status, data_revision"
    ") VALUES ("
    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
    ")"
)
DUCKDB_SELECT_MEASUREMENTS = (
    "SELECT measurement_id, timestamp, lot_id, wafer_id, slot, site_id, "
    "site_x_mm, site_y_mm, parameter_id, value, unit, step_id, tool_id, "
    "chamber_id, recipe_id, product_id, metrology_tool_id, "
    "measurement_status, data_revision FROM measurements"
)
DUCKDB_SELECT_BASELINE_BY_ID = (
    "SELECT baseline_id, parameter_id, status, n_observations, sigma_estimator, "
    "centre_line, lcl, ucl, sigma_estimate, sigma_multiplier, limits_unit, "
    "window_start, window_end, approved_by, approved_at, supersedes, "
    "effective_from FROM baselines WHERE baseline_id = ?"
)
DUCKDB_SELECT_ACTIVE_BASELINE = (
    "SELECT baseline_id, parameter_id, status, n_observations, sigma_estimator, "
    "centre_line, lcl, ucl, sigma_estimate, sigma_multiplier, limits_unit, "
    "window_start, window_end, approved_by, approved_at, supersedes, "
    "effective_from FROM baselines WHERE parameter_id = ? AND status = ? LIMIT 1"
)
DUCKDB_INSERT_BASELINE = (
    "INSERT INTO baselines ("
    "baseline_id, parameter_id, status, n_observations, sigma_estimator, "
    "centre_line, lcl, ucl, sigma_estimate, sigma_multiplier, limits_unit, "
    "window_start, window_end, approved_by, approved_at, supersedes, "
    "effective_from"
    ") VALUES ("
    "?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?"
    ")"
)
DUCKDB_LIST_BASELINES = (
    "SELECT baseline_id, parameter_id, status, n_observations, sigma_estimator, "
    "centre_line, lcl, ucl, sigma_estimate, sigma_multiplier, limits_unit, "
    "window_start, window_end, approved_by, approved_at, supersedes, "
    "effective_from FROM baselines WHERE parameter_id = ? "
    "ORDER BY effective_from DESC"
)
DUCKDB_LIST_BASELINES_BY_STATUS = (
    "SELECT baseline_id, parameter_id, status, n_observations, sigma_estimator, "
    "centre_line, lcl, ucl, sigma_estimate, sigma_multiplier, limits_unit, "
    "window_start, window_end, approved_by, approved_at, supersedes, "
    "effective_from FROM baselines WHERE parameter_id = ? AND status = ? "
    "ORDER BY effective_from DESC"
)

PG_INSERT_MEASUREMENT = (
    "INSERT INTO measurements ("
    "measurement_id, timestamp, lot_id, wafer_id, slot, site_id, "
    "site_x_mm, site_y_mm, parameter_id, value, unit, step_id, tool_id, "
    "chamber_id, recipe_id, product_id, metrology_tool_id, "
    "measurement_status, data_revision"
    ") VALUES ("
    ":measurement_id, :timestamp, :lot_id, :wafer_id, :slot, :site_id, "
    ":site_x_mm, :site_y_mm, :parameter_id, :value, :unit, :step_id, :tool_id, "
    ":chamber_id, :recipe_id, :product_id, :metrology_tool_id, "
    ":measurement_status, :data_revision"
    ")"
)
PG_SELECT_MEASUREMENTS = (
    "SELECT measurement_id, timestamp, lot_id, wafer_id, slot, site_id, "
    "site_x_mm, site_y_mm, parameter_id, value, unit, step_id, tool_id, "
    "chamber_id, recipe_id, product_id, metrology_tool_id, "
    "measurement_status, data_revision FROM measurements"
)
PG_SELECT_BASELINE_BY_ID = (
    "SELECT baseline_id, parameter_id, status, n_observations, sigma_estimator, "
    "centre_line, lcl, ucl, sigma_estimate, sigma_multiplier, limits_unit, "
    "window_start, window_end, approved_by, approved_at, supersedes, "
    "effective_from FROM baselines WHERE baseline_id = :baseline_id"
)
PG_SELECT_ACTIVE_BASELINE = (
    "SELECT baseline_id, parameter_id, status, n_observations, sigma_estimator, "
    "centre_line, lcl, ucl, sigma_estimate, sigma_multiplier, limits_unit, "
    "window_start, window_end, approved_by, approved_at, supersedes, "
    "effective_from FROM baselines "
    "WHERE parameter_id = :parameter_id AND status = :status LIMIT 1"
)
PG_INSERT_BASELINE = (
    "INSERT INTO baselines ("
    "baseline_id, parameter_id, status, n_observations, sigma_estimator, "
    "centre_line, lcl, ucl, sigma_estimate, sigma_multiplier, limits_unit, "
    "window_start, window_end, approved_by, approved_at, supersedes, "
    "effective_from"
    ") VALUES ("
    ":baseline_id, :parameter_id, :status, :n_observations, :sigma_estimator, "
    ":centre_line, :lcl, :ucl, :sigma_estimate, :sigma_multiplier, :limits_unit, "
    ":window_start, :window_end, :approved_by, :approved_at, :supersedes, "
    ":effective_from"
    ")"
)
PG_LIST_BASELINES = (
    "SELECT baseline_id, parameter_id, status, n_observations, sigma_estimator, "
    "centre_line, lcl, ucl, sigma_estimate, sigma_multiplier, limits_unit, "
    "window_start, window_end, approved_by, approved_at, supersedes, "
    "effective_from FROM baselines WHERE parameter_id = :parameter_id "
    "ORDER BY effective_from DESC"
)
PG_LIST_BASELINES_BY_STATUS = (
    "SELECT baseline_id, parameter_id, status, n_observations, sigma_estimator, "
    "centre_line, lcl, ucl, sigma_estimate, sigma_multiplier, limits_unit, "
    "window_start, window_end, approved_by, approved_at, supersedes, "
    "effective_from FROM baselines "
    "WHERE parameter_id = :parameter_id AND status = :status "
    "ORDER BY effective_from DESC"
)
