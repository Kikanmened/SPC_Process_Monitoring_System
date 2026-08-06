"""Filesystem measurement source materialises CSV and Parquet exports."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.factories.frames import a_raw_frame

from spc_platform.application.ports.measurement_source import BatchRequest
from spc_platform.common.errors import SourceUnavailableError
from spc_platform.infrastructure.readers.file_source import (
    FileMeasurementSource,
    load_raw_frame,
)


@pytest.mark.unit
def test_materialise_parquet_and_load(tmp_path: Path) -> None:
    source_path = tmp_path / "export.parquet"
    a_raw_frame().to_parquet(source_path, index=False)
    destination = tmp_path / "raw" / "batch.parquet"
    source = FileMeasurementSource(identity="unit://parquet")
    descriptor = source.materialise(BatchRequest(path=source_path), destination)
    assert destination.is_file()
    assert descriptor.format == "parquet"
    frame = load_raw_frame(destination)
    assert len(frame) == 1


@pytest.mark.unit
def test_missing_source_raises(tmp_path: Path) -> None:
    source = FileMeasurementSource()
    with pytest.raises(SourceUnavailableError):
        source.materialise(
            BatchRequest(path=tmp_path / "missing.parquet"),
            tmp_path / "out.parquet",
        )


@pytest.mark.unit
def test_expected_rows_mismatch_raises(tmp_path: Path) -> None:
    source_path = tmp_path / "export.parquet"
    a_raw_frame().to_parquet(source_path, index=False)
    source = FileMeasurementSource()
    with pytest.raises(SourceUnavailableError, match="row count"):
        source.materialise(
            BatchRequest(path=source_path, expected_rows=99),
            tmp_path / "out.parquet",
        )
