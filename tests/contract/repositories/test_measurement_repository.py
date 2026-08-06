"""Same MeasurementRepository contract on Fake, DuckDB, and PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from tests.factories.domain import a_measurement, aware

from spc_platform.application.ports.measurement_repository import (
    MeasurementRepository,
    SeriesQuery,
    WaferQuery,
)
from spc_platform.common.errors import InsufficientDataError
from spc_platform.domain.enums import MeasurementStatus
from spc_platform.domain.ids import DataRevision, LotId, ParameterId, WaferId
from spc_platform.infrastructure.repositories import (
    DuckDBMeasurementRepository,
    FakeMeasurementRepository,
    PostgresMeasurementRepository,
    apply_schema,
    create_postgres_engine,
)


@pytest.fixture(params=["fake", "duckdb", "postgres"])
def repository(request: pytest.FixtureRequest) -> Iterator[MeasurementRepository]:
    """Yield each adapter that implements the measurement port."""
    if request.param == "fake":
        yield FakeMeasurementRepository()
        return
    if request.param == "duckdb":
        adapter = DuckDBMeasurementRepository(path=None)
        try:
            yield adapter
        finally:
            adapter.close()
        return
    url = os.environ.get("SPC_TEST_DATABASE_URL")
    if not url:
        pytest.skip("SPC_TEST_DATABASE_URL not set")
    engine = create_postgres_engine(url)
    apply_schema(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("TRUNCATE TABLE measurements")
    yield PostgresMeasurementRepository(engine)


@pytest.mark.contract
def test_replace_revision_is_idempotent(repository: MeasurementRepository) -> None:
    revision = DataRevision("dr-contract-1")
    first = a_measurement(data_revision=revision, value=10.0)
    second = a_measurement(
        data_revision=revision,
        value=10.5,
        timestamp=aware() + timedelta(hours=1),
        site_id=2,
    )
    repository.replace_revision(revision, (first, second))
    repository.replace_revision(revision, (first,))
    series = repository.series_for(
        SeriesQuery(
            parameter_id=ParameterId("OXIDE_THK"),
            window_start=aware() - timedelta(days=1),
            window_end=aware() + timedelta(days=1),
            data_revision=revision,
        )
    )
    assert len(series.measurements) == 1
    assert series.measurements[0].value == 10.0
    assert repository.has_revision(revision) is True


@pytest.mark.contract
def test_series_excludes_superseded(repository: MeasurementRepository) -> None:
    revision = DataRevision("dr-contract-2")
    superseded = a_measurement(
        data_revision=revision,
        value=9.0,
        measurement_status=MeasurementStatus.SUPERSEDED,
        timestamp=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
    )
    kept = a_measurement(
        data_revision=revision,
        value=10.0,
        measurement_status=MeasurementStatus.REMEASURED,
        timestamp=datetime(2025, 6, 1, 11, 0, tzinfo=UTC),
        site_id=1,
    )
    repository.replace_revision(revision, (superseded, kept))
    series = repository.series_for(
        SeriesQuery(
            parameter_id=ParameterId("OXIDE_THK"),
            window_start=datetime(2025, 6, 1, tzinfo=UTC),
            window_end=datetime(2025, 6, 2, tzinfo=UTC),
            data_revision=revision,
        )
    )
    assert series.values() == (10.0,)


@pytest.mark.contract
def test_sites_for_orders_by_site_id(repository: MeasurementRepository) -> None:
    revision = DataRevision("dr-contract-3")
    site_2 = a_measurement(data_revision=revision, site_id=2, value=11.0)
    site_1 = a_measurement(data_revision=revision, site_id=1, value=10.0)
    repository.replace_revision(revision, (site_2, site_1))
    sites = repository.sites_for(
        WaferQuery(
            parameter_id=ParameterId("OXIDE_THK"),
            lot_id=LotId("LOT-001"),
            wafer_id=WaferId("LOT-001:1"),
            data_revision=revision,
        )
    )
    assert [int(item.site_id) for item in sites] == [1, 2]


@pytest.mark.contract
def test_empty_series_raises(repository: MeasurementRepository) -> None:
    with pytest.raises(InsufficientDataError):
        repository.series_for(
            SeriesQuery(
                parameter_id=ParameterId("MISSING"),
                window_start=aware(),
                window_end=aware() + timedelta(days=1),
            )
        )
