"""End-to-end: raw frame → interim → processed → repository query."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from tests.factories.frames import a_raw_frame, a_raw_row

from spc_platform.application.ports.measurement_repository import SeriesQuery
from spc_platform.common.time import FixedClock
from spc_platform.common.units import UnitRegistry
from spc_platform.domain.ids import ParameterId, UnitSymbol
from spc_platform.infrastructure.repositories.fake import FakeMeasurementRepository
from spc_platform.pipelines.paths import PipelinePaths
from spc_platform.pipelines.run import PipelineDependencies, run_pipeline


@pytest.mark.e2e
def test_pipeline_publishes_queryable_revision(tmp_path: Path) -> None:
    earlier = a_raw_row(
        measurement_id=str(uuid4()),
        timestamp=datetime(2025, 6, 1, 10, 0, tzinfo=UTC),
        value=9.9,
    )
    later = a_raw_row(
        measurement_id=str(uuid4()),
        timestamp=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
        value=10.1,
    )
    frame = a_raw_frame(earlier, later)
    repository = FakeMeasurementRepository()
    registry = UnitRegistry(units=frozenset({UnitSymbol("nm")}), conversions=())
    clock = FixedClock(datetime(2025, 6, 1, 13, 0, tzinfo=UTC))

    result = run_pipeline(
        frame,
        source_identity="e2e://remeasure",
        dependencies=PipelineDependencies(
            clock=clock,
            registry=registry,
            paths=PipelinePaths(
                quarantine_root=tmp_path / "quarantine",
                interim_directory=tmp_path / "interim",
                processed_directory=tmp_path / "processed",
            ),
            repository=repository,
        ),
    )

    assert result.publish.path is not None
    assert result.publish.path.is_file()
    assert result.ingestion.interim_path is not None
    assert (result.processing.frame["data_revision"] == str(result.data_revision)).all()

    series = repository.series_for(
        SeriesQuery(
            parameter_id=ParameterId("OXIDE_THK"),
            window_start=datetime(2025, 6, 1, tzinfo=UTC),
            window_end=datetime(2025, 6, 1, tzinfo=UTC) + timedelta(days=1),
            data_revision=result.data_revision,
        )
    )
    assert series.values() == (10.1,)
    assert len(result.processing.frame) == 2
