"""Measurement key uniqueness (FR-D10)."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from spc_platform.common.errors import DuplicateMeasurementKeyError

DEFAULT_MEASUREMENT_KEY: tuple[str, ...] = (
    "lot_id",
    "wafer_id",
    "site_id",
    "parameter_id",
    "timestamp",
    "metrology_tool_id",
)


def find_duplicate_keys(
    frame: pd.DataFrame,
    key_columns: Sequence[str] = DEFAULT_MEASUREMENT_KEY,
) -> pd.DataFrame:
    """Return the rows whose key appears more than once."""
    missing = [column for column in key_columns if column not in frame.columns]
    if missing:
        raise DuplicateMeasurementKeyError(
            "measurement key references columns absent from the batch",
            missing=missing,
        )
    duplicated = frame.duplicated(subset=list(key_columns), keep=False)
    return frame.loc[duplicated]


def require_unique_keys(
    frame: pd.DataFrame,
    key_columns: Sequence[str] = DEFAULT_MEASUREMENT_KEY,
) -> None:
    """Raise if the measurement key is not unique within the batch.

    Duplicates are never dropped. Silent de-duplication would hide an export
    defect and admit an incomplete history.
    """
    collisions = find_duplicate_keys(frame, key_columns)
    if collisions.empty:
        return
    sample = collisions.loc[:, list(key_columns)].head(5).to_dict(orient="records")
    raise DuplicateMeasurementKeyError(
        "measurement key is not unique within the batch",
        key_columns=list(key_columns),
        collision_count=len(collisions),
        sample=sample,
    )
