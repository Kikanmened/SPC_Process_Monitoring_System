"""Repository adapters behind application ports (ADR-0008)."""

from spc_platform.infrastructure.repositories.duckdb_store import (
    DuckDBBaselineStore,
    DuckDBMeasurementRepository,
)
from spc_platform.infrastructure.repositories.fake import (
    FakeBaselineStore,
    FakeMeasurementRepository,
)
from spc_platform.infrastructure.repositories.postgres_store import (
    PostgresBaselineStore,
    PostgresMeasurementRepository,
    apply_schema,
    create_postgres_engine,
)

__all__ = [
    "DuckDBBaselineStore",
    "DuckDBMeasurementRepository",
    "FakeBaselineStore",
    "FakeMeasurementRepository",
    "PostgresBaselineStore",
    "PostgresMeasurementRepository",
    "apply_schema",
    "create_postgres_engine",
]
