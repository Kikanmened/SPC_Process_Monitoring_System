"""Content digests and on-disk round trips.

The digest is what makes the reproduction guarantee checkable without comparing
file bytes, which would tie the guarantee to a Parquet writer version rather
than to the data.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from spc_platform.domain.enums import MeasurementStatus
from spc_platform.simulation.exporters import (
    DatasetFormat,
    content_digest,
    read_measurements,
)
from spc_platform.simulation.generator import RAW_COLUMNS


def a_frame(rows: int = 8) -> pd.DataFrame:
    """Build a small frame with the raw-zone columns and dtypes."""
    index = np.arange(rows)
    return pd.DataFrame(
        {
            "measurement_id": [f"id-{i:04d}" for i in index],
            "timestamp": pd.date_range("2025-01-01", periods=rows, freq="h", tz="UTC"),
            "lot_id": [f"LOT{i // 4:03d}" for i in index],
            "wafer_id": [f"WFR{i:03d}" for i in index],
            "slot": (index % 25 + 1).astype("int16"),
            "site_id": (index % 5 + 1).astype("int16"),
            "site_x": index * 1.5 - 3.0,
            "site_y": index * -0.25,
            "parameter_id": ["POLY_CD"] * rows,
            "value": 100.0 + index * 0.123_456_789_012_345,
            "unit": ["nm"] * rows,
            "step_id": ["POLY_ETCH"] * rows,
            "tool_id": ["ETC-01"] * rows,
            "chamber_id": ["ETC-01-A"] * rows,
            "recipe_id": ["RCP-POLY_ETCH-DEV-A"] * rows,
            "product_id": ["DEV-A"] * rows,
            "metrology_tool_id": ["MET-CDSEM-01"] * rows,
            "measurement_status": [MeasurementStatus.VALID.value] * rows,
        }
    ).loc[:, list(RAW_COLUMNS)]


class TestContentDigest:
    """Hashing a frame's contents."""

    def test_identical_frames_digest_identically(self) -> None:
        assert content_digest(a_frame()) == content_digest(a_frame())

    def test_a_changed_value_changes_the_digest(self) -> None:
        changed = a_frame()
        changed.loc[3, "value"] = changed["value"].iloc[3] + 1e-9

        assert content_digest(changed) != content_digest(a_frame())

    def test_a_changed_identifier_changes_the_digest(self) -> None:
        """String columns are hashed as text.

        Hashing their numpy buffer would hash pointer addresses, which differ on every run.
        """
        changed = a_frame()
        changed.loc[3, "tool_id"] = "ETC-02"

        assert content_digest(changed) != content_digest(a_frame())

    def test_reordering_rows_changes_the_digest(self) -> None:
        """Row order is part of the reproduction guarantee, not incidental."""
        reversed_frame = a_frame().iloc[::-1].reset_index(drop=True)

        assert content_digest(reversed_frame) != content_digest(a_frame())

    def test_a_changed_timestamp_changes_the_digest(self) -> None:
        changed = a_frame()
        changed.loc[3, "timestamp"] = changed["timestamp"].iloc[3] + pd.Timedelta(seconds=1)

        assert content_digest(changed) != content_digest(a_frame())

    def test_a_missing_value_is_distinguished_from_a_present_one(self) -> None:
        changed = a_frame()
        changed.loc[3, "value"] = np.nan

        assert content_digest(changed) != content_digest(a_frame())


class TestRoundTrip:
    """Writing and reading back."""

    @pytest.mark.parametrize("dataset_format", list(DatasetFormat))
    def test_the_digest_survives_a_round_trip(
        self,
        dataset_format: DatasetFormat,
        tmp_path: Path,
    ) -> None:
        """Both formats must be lossless.

        A CSV that dropped a unit in the last place would make every digest taken from it disagree
        with the manifest.
        """
        frame = a_frame()
        path = tmp_path / f"measurements{dataset_format.suffix}"
        if dataset_format is DatasetFormat.PARQUET:
            frame.to_parquet(path, index=False)
        else:
            frame.to_csv(path, index=False, date_format="%Y-%m-%dT%H:%M:%S%z", float_format="%.17g")

        assert content_digest(read_measurements(path)) == content_digest(frame)

    @pytest.mark.parametrize("dataset_format", list(DatasetFormat))
    def test_columns_come_back_in_raw_zone_order(
        self,
        dataset_format: DatasetFormat,
        tmp_path: Path,
    ) -> None:
        frame = a_frame()
        path = tmp_path / f"measurements{dataset_format.suffix}"
        shuffled = frame.loc[:, list(reversed(RAW_COLUMNS))]
        if dataset_format is DatasetFormat.PARQUET:
            shuffled.to_parquet(path, index=False)
        else:
            shuffled.to_csv(path, index=False, date_format="%Y-%m-%dT%H:%M:%S%z")

        assert tuple(read_measurements(path).columns) == RAW_COLUMNS

    @pytest.mark.parametrize("dataset_format", list(DatasetFormat))
    def test_timestamps_come_back_timezone_aware(
        self,
        dataset_format: DatasetFormat,
        tmp_path: Path,
    ) -> None:
        """A timestamp keeps its timezone across the storage boundary.

        A naive timestamp is rejected at ingest, so a lossy reader would make
        a valid dataset unloadable.
        """
        frame = a_frame()
        path = tmp_path / f"measurements{dataset_format.suffix}"
        if dataset_format is DatasetFormat.PARQUET:
            frame.to_parquet(path, index=False)
        else:
            frame.to_csv(path, index=False, date_format="%Y-%m-%dT%H:%M:%S%z")

        assert read_measurements(path)["timestamp"].dt.tz is not None


def test_the_format_suffix_matches_its_name() -> None:
    assert DatasetFormat.PARQUET.suffix == ".parquet"
    assert DatasetFormat.CSV.suffix == ".csv"
