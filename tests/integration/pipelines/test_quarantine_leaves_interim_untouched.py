"""A malformed batch never leaves residue in the interim zone (NFR-R04)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.factories.frames import a_raw_frame, a_raw_row

from spc_platform.common.errors import SchemaValidationError
from spc_platform.common.time import FixedClock
from spc_platform.pipelines.ingest import ingest_batch
from spc_platform.pipelines.paths import PipelinePaths


@pytest.mark.integration
def test_failed_ingest_writes_quarantine_only(tmp_path: Path) -> None:
    frame = a_raw_frame(a_raw_row(site_x=500.0, site_y=0.0))
    interim = tmp_path / "interim"
    interim.mkdir()
    sentinel = interim / "pre-existing.parquet"
    sentinel.write_bytes(b"keep")
    paths = PipelinePaths(
        quarantine_root=tmp_path / "quarantine",
        interim_directory=interim,
    )
    clock = FixedClock(datetime(2025, 6, 1, 12, 0, tzinfo=UTC))

    with pytest.raises(SchemaValidationError):
        ingest_batch(
            frame,
            source_identity="integration://bad",
            clock=clock,
            paths=paths,
        )

    assert sentinel.is_file()
    assert list(interim.iterdir()) == [sentinel]
    assert any(paths.quarantine_root.iterdir())
