"""Builders for measurement DataFrames used by pipeline tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pandas as pd


def a_raw_row(**overrides: object) -> dict[str, object]:
    """One valid raw-zone measurement row."""
    row: dict[str, object] = {
        "measurement_id": str(uuid4()),
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
    row.update(overrides)
    return row


def a_raw_frame(*rows: dict[str, object]) -> pd.DataFrame:
    """Build a raw frame from zero or more row dicts (defaults to one)."""
    if not rows:
        return pd.DataFrame([a_raw_row()])
    return pd.DataFrame(list(rows))
