"""Pandera schemas reject malformed measurement batches (FR-D02, FR-D03)."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd
import pytest
from pandera.errors import SchemaError, SchemaErrors

from spc_platform.pipelines.schemas import (
    ProcessedMeasurementSchema,
    RawMeasurementSchema,
)


def _valid_frame(*, with_revision: bool = False) -> pd.DataFrame:
    row = {
        "measurement_id": "m-1",
        "timestamp": datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
        "lot_id": "LOT-1",
        "wafer_id": "LOT-1:1",
        "slot": 1,
        "site_id": 1,
        "site_x": 0.0,
        "site_y": 0.0,
        "parameter_id": "OXIDE_THK",
        "value": 10.0,
        "unit": "nm",
        "step_id": "OXIDE_GROW",
        "tool_id": "OX-01",
        "chamber_id": "OX-01-A",
        "recipe_id": "OX-STD-1",
        "product_id": "DEV-A",
        "metrology_tool_id": "MET-ELLIP-01",
        "measurement_status": "valid",
    }
    if with_revision:
        row["data_revision"] = "rev-1"
    return pd.DataFrame([row])


@pytest.mark.unit
def test_raw_schema_accepts_valid_batch() -> None:
    RawMeasurementSchema.validate(_valid_frame())


@pytest.mark.unit
def test_raw_schema_rejects_unknown_column() -> None:
    frame = _valid_frame()
    frame["extra"] = 1
    with pytest.raises((SchemaError, SchemaErrors)):
        RawMeasurementSchema.validate(frame)


@pytest.mark.unit
def test_raw_schema_rejects_slot_out_of_range() -> None:
    frame = _valid_frame()
    frame.loc[0, "slot"] = 26
    with pytest.raises((SchemaError, SchemaErrors)):
        RawMeasurementSchema.validate(frame)


@pytest.mark.unit
def test_raw_schema_rejects_site_outside_wafer() -> None:
    frame = _valid_frame()
    frame.loc[0, "site_x"] = 200.0
    with pytest.raises((SchemaError, SchemaErrors)):
        RawMeasurementSchema.validate(frame)


@pytest.mark.unit
def test_processed_schema_requires_data_revision() -> None:
    with pytest.raises((SchemaError, SchemaErrors)):
        ProcessedMeasurementSchema.validate(_valid_frame(with_revision=False))


@pytest.mark.unit
def test_processed_schema_accepts_valid_batch() -> None:
    ProcessedMeasurementSchema.validate(_valid_frame(with_revision=True))
