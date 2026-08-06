"""PostgreSQL adapters for measurement and baseline persistence (ADR-0008)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

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
    PG_INSERT_BASELINE,
    PG_INSERT_MEASUREMENT,
    PG_LIST_BASELINES,
    PG_LIST_BASELINES_BY_STATUS,
    PG_SELECT_ACTIVE_BASELINE,
    PG_SELECT_BASELINE_BY_ID,
    PG_SELECT_MEASUREMENTS,
)


def create_postgres_engine(url: str) -> Engine:
    """Build a SQLAlchemy engine for the given PostgreSQL URL."""
    return create_engine(url, future=True)


def apply_schema(engine: Engine) -> None:
    """Create measurement and baseline tables if they do not exist.

    Production deploys use Alembic. This helper exists for contract tests and
    ephemeral databases that apply the same DDL the migration embeds.
    """
    with engine.begin() as connection:
        connection.execute(text(MEASUREMENTS_DDL))
        for statement in MEASUREMENTS_INDEXES:
            connection.execute(text(statement))
        connection.execute(text(BASELINES_DDL))
        for statement in BASELINES_INDEXES:
            connection.execute(text(statement))


class PostgresMeasurementRepository:
    """PostgreSQL-backed ``MeasurementRepository``."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

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
        insert_sql = text(PG_INSERT_MEASUREMENT)
        with self._engine.begin() as connection:
            connection.execute(
                text("DELETE FROM measurements WHERE data_revision = :revision"),
                {"revision": str(revision)},
            )
            for item in measurements:
                connection.execute(insert_sql, measurement_to_row(item))

    def series_for(self, query: SeriesQuery) -> MeasurementSeries:
        """Return the matching series, time-ordered."""
        return series_from_measurements(query, self._load_all())

    def sites_for(self, query: WaferQuery) -> tuple[Measurement, ...]:
        """Return every chartable site on the wafer for the parameter."""
        return filter_sites(self._load_all(), query)

    def has_revision(self, revision: DataRevision) -> bool:
        """Return whether any row carries ``revision``."""
        with self._engine.connect() as connection:
            result = connection.execute(
                text("SELECT 1 FROM measurements WHERE data_revision = :revision LIMIT 1"),
                {"revision": str(revision)},
            ).first()
        return result is not None

    def _load_all(self) -> tuple[Measurement, ...]:
        sql = text(PG_SELECT_MEASUREMENTS)
        with self._engine.connect() as connection:
            rows = connection.execute(sql).mappings().all()
        return tuple(measurement_from_row(dict(row)) for row in rows)


class PostgresBaselineStore:
    """PostgreSQL-backed ``BaselineStore``."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, baseline_id: BaselineId) -> Baseline | None:
        """Return the baseline, or None if unknown."""
        sql = text(PG_SELECT_BASELINE_BY_ID)
        with self._engine.connect() as connection:
            row = connection.execute(sql, {"baseline_id": str(baseline_id)}).mappings().first()
        if row is None:
            return None
        return baseline_from_row(dict(row))

    def active_for(self, parameter_id: ParameterId) -> Baseline | None:
        """Return the active baseline for the parameter, if any."""
        sql = text(PG_SELECT_ACTIVE_BASELINE)
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    sql,
                    {
                        "parameter_id": str(parameter_id),
                        "status": BaselineStatus.ACTIVE.value,
                    },
                )
                .mappings()
                .first()
            )
        if row is None:
            return None
        return baseline_from_row(dict(row))

    def save(self, baseline: Baseline) -> None:
        """Store a baseline; activating one supersedes the previous active."""
        if self.get(baseline.baseline_id) is not None:
            message = "baselines are immutable once saved"
            raise ValueError(message)

        insert_sql = text(PG_INSERT_BASELINE)
        payload: dict[str, Any] = baseline_to_row(baseline)
        with self._engine.begin() as connection:
            if baseline.status is BaselineStatus.ACTIVE:
                connection.execute(
                    text(
                        """
                        UPDATE baselines
                        SET status = :superseded
                        WHERE parameter_id = :parameter_id AND status = :active
                        """
                    ),
                    {
                        "superseded": BaselineStatus.SUPERSEDED.value,
                        "parameter_id": str(baseline.parameter_id),
                        "active": BaselineStatus.ACTIVE.value,
                    },
                )
            connection.execute(insert_sql, payload)

    def list_for(
        self,
        parameter_id: ParameterId,
        *,
        status: BaselineStatus | None = None,
    ) -> tuple[Baseline, ...]:
        """Return baselines for the parameter, newest effective_from first."""
        if status is None:
            sql = text(PG_LIST_BASELINES)
            params: dict[str, Any] = {"parameter_id": str(parameter_id)}
        else:
            sql = text(PG_LIST_BASELINES_BY_STATUS)
            params = {"parameter_id": str(parameter_id), "status": status.value}
        with self._engine.connect() as connection:
            rows = connection.execute(sql, params).mappings().all()
        return tuple(baseline_from_row(dict(row)) for row in rows)
