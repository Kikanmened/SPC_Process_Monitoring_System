"""Measurement schemas for the raw, interim, and processed zones.

The grain is one measurement of one parameter at one site on one wafer at one
time (DATASET_GUIDE.md §3.1). Zone differences:

* **raw** — as exported; units may still need normalisation.
* **interim** — pipeline-internal; carries ``data_revision``.
* **processed** — analysis-ready single source of truth.
"""

from __future__ import annotations

import pandera.pandas as pa

WAFER_RADIUS_MM = 150.0

_MEASUREMENT_STATUSES = ("valid", "remeasured", "superseded", "suspect")

_COMMON_COLUMNS: dict[str, pa.Column] = {
    "measurement_id": pa.Column(str, nullable=False, unique=True),
    "timestamp": pa.Column(pa.DateTime, nullable=False, coerce=True),
    "lot_id": pa.Column(str, nullable=False),
    "wafer_id": pa.Column(str, nullable=False),
    "slot": pa.Column(int, pa.Check.in_range(1, 25), nullable=False, coerce=True),
    "site_id": pa.Column(int, pa.Check.ge(1), nullable=False, coerce=True),
    "site_x": pa.Column(float, nullable=False, coerce=True),
    "site_y": pa.Column(float, nullable=False, coerce=True),
    "parameter_id": pa.Column(str, nullable=False),
    "value": pa.Column(float, nullable=False, coerce=True),
    "unit": pa.Column(str, nullable=False),
    "step_id": pa.Column(str, nullable=False),
    "tool_id": pa.Column(str, nullable=False),
    "chamber_id": pa.Column(str, nullable=False),
    "recipe_id": pa.Column(str, nullable=False),
    "product_id": pa.Column(str, nullable=False),
    "metrology_tool_id": pa.Column(str, nullable=False),
    "measurement_status": pa.Column(
        str,
        pa.Check.isin(list(_MEASUREMENT_STATUSES)),
        nullable=False,
    ),
}


def _site_within_wafer(df: object) -> bool:
    """Return True when every site lies inside the 300 mm wafer radius."""
    frame = df
    xs = frame["site_x"]  # type: ignore[index]
    ys = frame["site_y"]  # type: ignore[index]
    return bool(((xs**2 + ys**2) <= WAFER_RADIUS_MM**2).all())


def _build_schema(*, require_data_revision: bool, name: str) -> pa.DataFrameSchema:
    columns = dict(_COMMON_COLUMNS)
    if require_data_revision:
        columns["data_revision"] = pa.Column(str, nullable=False)
    return pa.DataFrameSchema(
        columns,
        checks=[pa.Check(_site_within_wafer, error="site outside wafer radius")],
        coerce=False,
        strict=True,
        name=name,
    )


RawMeasurementSchema = _build_schema(require_data_revision=False, name="raw_measurement")
InterimMeasurementSchema = _build_schema(
    require_data_revision=True,
    name="interim_measurement",
)
ProcessedMeasurementSchema = _build_schema(
    require_data_revision=True,
    name="processed_measurement",
)
