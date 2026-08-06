"""Same BaselineStore contract on Fake, DuckDB, and PostgreSQL."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import timedelta

import pytest
from tests.factories.domain import a_baseline, a_control_limit, aware

from spc_platform.application.ports.baseline_store import BaselineStore
from spc_platform.domain.baseline import Baseline
from spc_platform.domain.enums import BaselineStatus
from spc_platform.domain.ids import BaselineId, ParameterId
from spc_platform.infrastructure.repositories import (
    DuckDBBaselineStore,
    FakeBaselineStore,
    PostgresBaselineStore,
    apply_schema,
    create_postgres_engine,
)


def _baseline(baseline_id: str, **overrides: object) -> Baseline:
    limits = a_control_limit(baseline_id=BaselineId(baseline_id))
    payload: dict[str, object] = {
        "baseline_id": BaselineId(baseline_id),
        "limits": limits,
    }
    payload.update(overrides)
    return a_baseline(**payload)


@pytest.fixture(params=["fake", "duckdb", "postgres"])
def store(request: pytest.FixtureRequest) -> Iterator[BaselineStore]:
    """Yield each adapter that implements the baseline port."""
    if request.param == "fake":
        yield FakeBaselineStore()
        return
    if request.param == "duckdb":
        adapter = DuckDBBaselineStore(path=None)
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
        connection.exec_driver_sql("TRUNCATE TABLE baselines")
    yield PostgresBaselineStore(engine)


@pytest.mark.contract
def test_activate_supersedes_previous(store: BaselineStore) -> None:
    first = _baseline(
        "BL-1",
        status=BaselineStatus.ACTIVE,
        effective_from=aware(month=7, day=1),
    )
    second = _baseline(
        "BL-2",
        status=BaselineStatus.ACTIVE,
        supersedes=BaselineId("BL-1"),
        effective_from=aware(month=8, day=1),
        window_start=aware(month=7, day=1),
        window_end=aware(month=7, day=28),
    )
    store.save(first)
    store.save(second)
    active = store.active_for(ParameterId("OXIDE_THK"))
    assert active is not None
    assert active.baseline_id == BaselineId("BL-2")
    previous = store.get(BaselineId("BL-1"))
    assert previous is not None
    assert previous.status is BaselineStatus.SUPERSEDED


@pytest.mark.contract
def test_baselines_are_immutable(store: BaselineStore) -> None:
    baseline = _baseline("BL-IMM")
    store.save(baseline)
    with pytest.raises(ValueError, match="immutable"):
        store.save(baseline)


@pytest.mark.contract
def test_list_for_orders_newest_first(store: BaselineStore) -> None:
    older = _baseline(
        "BL-OLD",
        status=BaselineStatus.CANDIDATE,
        approved_by=None,
        approved_at=None,
        effective_from=aware(month=6, day=1),
    )
    newer = _baseline(
        "BL-NEW",
        status=BaselineStatus.CANDIDATE,
        approved_by=None,
        approved_at=None,
        effective_from=aware(month=6, day=1) + timedelta(days=10),
        window_start=aware(month=5, day=1),
        window_end=aware(month=5, day=28),
    )
    store.save(older)
    store.save(newer)
    listed = store.list_for(ParameterId("OXIDE_THK"))
    assert [item.baseline_id for item in listed] == [
        BaselineId("BL-NEW"),
        BaselineId("BL-OLD"),
    ]
