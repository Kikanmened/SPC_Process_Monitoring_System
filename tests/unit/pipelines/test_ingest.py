"""Ingest validates, quarantines, and assigns data_revision (FR-D02-D04, D09-D10)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from tests.factories.frames import a_raw_frame, a_raw_row

from spc_platform.common.errors import (
    DuplicateMeasurementKeyError,
    NaiveDatetimeError,
    SchemaValidationError,
)
from spc_platform.common.time import FixedClock
from spc_platform.pipelines.ingest import ingest_batch
from spc_platform.pipelines.lineage import data_revision_for
from spc_platform.pipelines.paths import PipelinePaths


def _paths(tmp_path: Path, *, interim: bool = True) -> PipelinePaths:
    return PipelinePaths(
        quarantine_root=tmp_path / "quarantine",
        interim_directory=(tmp_path / "interim") if interim else None,
    )


@pytest.mark.unit
def test_ingest_assigns_content_addressed_revision(tmp_path: Path) -> None:
    frame = a_raw_frame()
    clock = FixedClock(datetime(2025, 6, 1, 12, 0, tzinfo=UTC))
    result = ingest_batch(
        frame,
        source_identity="test://batch",
        clock=clock,
        paths=_paths(tmp_path),
    )
    assert str(result.data_revision).startswith("dr-")
    assert result.data_revision == data_revision_for(frame)
    assert (result.frame["data_revision"] == str(result.data_revision)).all()
    assert result.interim_path is not None
    assert result.interim_path.is_file()
    assert result.run.succeeded is True


@pytest.mark.unit
def test_reingest_same_bytes_same_revision(tmp_path: Path) -> None:
    frame = a_raw_frame()
    clock = FixedClock(datetime(2025, 6, 1, 12, 0, tzinfo=UTC))
    first = ingest_batch(
        frame,
        source_identity="test://batch",
        clock=clock,
        paths=_paths(tmp_path, interim=False),
    )
    second = ingest_batch(
        frame,
        source_identity="test://batch",
        clock=clock,
        paths=_paths(tmp_path, interim=False),
    )
    assert first.data_revision == second.data_revision
    assert first.run.run_id != second.run.run_id


@pytest.mark.unit
def test_schema_failure_quarantines_and_skips_interim(tmp_path: Path) -> None:
    frame = a_raw_frame(a_raw_row(slot=99))
    paths = _paths(tmp_path)
    clock = FixedClock(datetime(2025, 6, 1, 12, 0, tzinfo=UTC))
    with pytest.raises(SchemaValidationError) as captured:
        ingest_batch(
            frame,
            source_identity="test://bad",
            clock=clock,
            paths=paths,
        )
    assert "quarantine" in captured.value.context
    quarantine_dir = Path(str(captured.value.context["quarantine"]))
    assert quarantine_dir.is_dir()
    assert (quarantine_dir / "rejected_batch.parquet").is_file()
    assert (quarantine_dir / "validation_report.json").is_file()
    interim = paths.interim_directory
    assert interim is not None
    assert not interim.exists() or not any(interim.iterdir())


@pytest.mark.unit
def test_naive_timestamp_is_rejected(tmp_path: Path) -> None:
    naive = datetime(2025, 6, 1, 12, 0)  # noqa: DTZ001 — deliberate naive input
    frame = a_raw_frame(a_raw_row(timestamp=naive))
    clock = FixedClock(datetime(2025, 6, 1, 12, 0, tzinfo=UTC))
    with pytest.raises(NaiveDatetimeError):
        ingest_batch(
            frame,
            source_identity="test://naive",
            clock=clock,
            paths=_paths(tmp_path, interim=False),
        )


@pytest.mark.unit
def test_duplicate_key_fails_the_run(tmp_path: Path) -> None:
    row = a_raw_row()
    duplicate = a_raw_row(**{**row, "measurement_id": str(uuid4())})
    frame = a_raw_frame(row, duplicate)
    clock = FixedClock(datetime(2025, 6, 1, 12, 0, tzinfo=UTC))
    with pytest.raises(DuplicateMeasurementKeyError):
        ingest_batch(
            frame,
            source_identity="test://dup",
            clock=clock,
            paths=_paths(tmp_path, interim=False),
        )
