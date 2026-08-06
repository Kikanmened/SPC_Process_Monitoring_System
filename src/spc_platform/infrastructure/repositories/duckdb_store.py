"""DuckDB adapters for local measurement and baseline persistence (ADR-0008)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import duckdb

from spc_platform.application.ports.measurement_repository import SeriesQuery, WaferQuery
from spc_platform.domain.baseline import Baseline
from spc_platform.domain.enums import BaselineStatus
from spc_platform.domain.ids import BaselineId, DataRevision, ParameterId
from spc_platform.domain.measurement import Measurement
from spc_platform.domain.measurement_series import MeasurementSeries
from spc_platform.infrastructure.repositories.ddl import (
    BASELINES_DDL,
    BASELINES_INDEXES,
    MEASUREMENTS_DDL,
    MEASUREMENTS_INDEXES,
)
from spc_platform.infrastructure.repositories.row_mapping import (
    BASELINE_COLUMNS,
    MEASUREMENT_COLUMNS,
    baseline_from_row,
    baseline_to_row,
    measurement_from_row,
    measurement_to_row,
)
from spc_platform.infrastructure.repositories.series_query import (
    filter_sites,
    series_from_measurements,
)
from spc_platform.infrastructure.repositories.sql_text import (
    DUCKDB_INSERT_BASELINE,
    DUCKDB_INSERT_MEASUREMENT,
    DUCKDB_LIST_BASELINES,
    DUCKDB_LIST_BASELINES_BY_STATUS,
    DUCKDB_SELECT_ACTIVE_BASELINE,
    DUCKDB_SELECT_BASELINE_BY_ID,
    DUCKDB_SELECT_MEASUREMENTS,
)


def _connect(path: Path | None) -> duckdb.DuckDBPyConnection:
    if path is None:
        return duckdb.connect(database=":memory:")
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(database=str(path))


class DuckDBMeasurementRepository:
    """DuckDB-backed ``MeasurementRepository``."""

    def __init__(self, path: Path | None = None) -> None:
        self._connection = _connect(path)
        self._connection.execute(MEASUREMENTS_DDL)
        for statement in MEASUREMENTS_INDEXES:
            self._connection.execute(statement)

    def close(self) -> None:
        """Close the underlying connection."""
        self._connection.close()

    def replace_revision(
        self,
        revision: DataRevision,
        measurements: Sequence[Measurement],
    ) -> None:
        """Replace all rows for ``revision`` in one transaction."""
        for item in measurements:
            if item.data_revision != revision:
                message = "measurement data_revision must match replace_revision argument"
                raise ValueError(message)
        self._connection.execute("BEGIN TRANSACTION")
        try:
            self._connection.execute(
                "DELETE FROM measurements WHERE data_revision = ?",
                [str(revision)],
            )
            for item in measurements:
                row = measurement_to_row(item)
                values = [row[column] for column in MEASUREMENT_COLUMNS]
                self._connection.execute(DUCKDB_INSERT_MEASUREMENT, values)
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def series_for(self, query: SeriesQuery) -> MeasurementSeries:
        """Return the matching series, time-ordered."""
        return series_from_measurements(query, self._load_all())

    def sites_for(self, query: WaferQuery) -> tuple[Measurement, ...]:
        """Return every chartable site on the wafer for the parameter."""
        return filter_sites(self._load_all(), query)

    def has_revision(self, revision: DataRevision) -> bool:
        """Return whether any row carries ``revision``."""
        result = self._connection.execute(
            "SELECT 1 FROM measurements WHERE data_revision = ? LIMIT 1",
            [str(revision)],
        ).fetchone()
        return result is not None

    def _load_all(self) -> tuple[Measurement, ...]:
        result = self._connection.execute(DUCKDB_SELECT_MEASUREMENTS).fetchall()
        rows = [_row_dict(MEASUREMENT_COLUMNS, values) for values in result]
        return tuple(measurement_from_row(row) for row in rows)


class DuckDBBaselineStore:
    """DuckDB-backed ``BaselineStore``."""

    def __init__(self, path: Path | None = None) -> None:
        self._connection = _connect(path)
        self._connection.execute(BASELINES_DDL)
        for statement in BASELINES_INDEXES:
            self._connection.execute(statement)

    def close(self) -> None:
        """Close the underlying connection."""
        self._connection.close()

    def get(self, baseline_id: BaselineId) -> Baseline | None:
        """Return the baseline, or None if unknown."""
        result = self._connection.execute(
            DUCKDB_SELECT_BASELINE_BY_ID,
            [str(baseline_id)],
        ).fetchone()
        if result is None:
            return None
        return baseline_from_row(_row_dict(BASELINE_COLUMNS, result))

    def active_for(self, parameter_id: ParameterId) -> Baseline | None:
        """Return the active baseline for the parameter, if any."""
        result = self._connection.execute(
            DUCKDB_SELECT_ACTIVE_BASELINE,
            [str(parameter_id), BaselineStatus.ACTIVE.value],
        ).fetchone()
        if result is None:
            return None
        return baseline_from_row(_row_dict(BASELINE_COLUMNS, result))

    def save(self, baseline: Baseline) -> None:
        """Store a baseline; activating one supersedes the previous active."""
        existing = self.get(baseline.baseline_id)
        if existing is not None:
            message = "baselines are immutable once saved"
            raise ValueError(message)

        self._connection.execute("BEGIN TRANSACTION")
        try:
            if baseline.status is BaselineStatus.ACTIVE:
                self._connection.execute(
                    """
                    UPDATE baselines
                    SET status = ?
                    WHERE parameter_id = ? AND status = ?
                    """,
                    [
                        BaselineStatus.SUPERSEDED.value,
                        str(baseline.parameter_id),
                        BaselineStatus.ACTIVE.value,
                    ],
                )
            row = baseline_to_row(baseline)
            values = [row[column] for column in BASELINE_COLUMNS]
            self._connection.execute(DUCKDB_INSERT_BASELINE, values)
            self._connection.execute("COMMIT")
        except Exception:
            self._connection.execute("ROLLBACK")
            raise

    def list_for(
        self,
        parameter_id: ParameterId,
        *,
        status: BaselineStatus | None = None,
    ) -> tuple[Baseline, ...]:
        """Return baselines for the parameter, newest effective_from first."""
        if status is None:
            result = self._connection.execute(
                DUCKDB_LIST_BASELINES,
                [str(parameter_id)],
            ).fetchall()
        else:
            result = self._connection.execute(
                DUCKDB_LIST_BASELINES_BY_STATUS,
                [str(parameter_id), status.value],
            ).fetchall()
        return tuple(baseline_from_row(_row_dict(BASELINE_COLUMNS, values)) for values in result)


def _row_dict(columns: tuple[str, ...], values: Sequence[Any]) -> dict[str, Any]:
    return dict(zip(columns, values, strict=True))
