"""Convert between Pandera zone frames and domain ``Measurement`` values.

Column names differ on purpose: the wire format uses ``site_x`` / ``site_y``
(DATASET_GUIDE.md); the domain model uses ``site_x_mm`` / ``site_y_mm`` so a
reader never wonders whether the number is millimetres or die indices.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import pandas as pd

from spc_platform.domain.enums import MeasurementStatus
from spc_platform.domain.ids import (
    ChamberId,
    DataRevision,
    LotId,
    MeasurementId,
    MetrologyToolId,
    ParameterId,
    ProductId,
    RecipeId,
    SiteId,
    StepId,
    ToolId,
    UnitSymbol,
    WaferId,
)
from spc_platform.domain.measurement import Measurement


def _as_aware_utc(value: object) -> datetime:
    timestamp = pd.Timestamp(cast("Any", value))
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(UTC)
    else:
        timestamp = timestamp.tz_convert(UTC)
    return timestamp.to_pydatetime()


def measurements_from_frame(frame: pd.DataFrame) -> tuple[Measurement, ...]:
    """Build domain measurements from a processed/interim frame."""
    rows: list[Measurement] = []
    for record in frame.to_dict(orient="records"):
        rows.append(
            Measurement(
                measurement_id=MeasurementId(UUID(str(record["measurement_id"]))),
                timestamp=_as_aware_utc(record["timestamp"]),
                lot_id=LotId(str(record["lot_id"])),
                wafer_id=WaferId(str(record["wafer_id"])),
                slot=int(cast("Any", record["slot"])),
                site_id=SiteId(int(cast("Any", record["site_id"]))),
                site_x_mm=float(cast("Any", record["site_x"])),
                site_y_mm=float(cast("Any", record["site_y"])),
                parameter_id=ParameterId(str(record["parameter_id"])),
                value=float(cast("Any", record["value"])),
                unit=UnitSymbol(str(record["unit"])),
                step_id=StepId(str(record["step_id"])),
                tool_id=ToolId(str(record["tool_id"])),
                chamber_id=ChamberId(str(record["chamber_id"])),
                recipe_id=RecipeId(str(record["recipe_id"])),
                product_id=ProductId(str(record["product_id"])),
                metrology_tool_id=MetrologyToolId(str(record["metrology_tool_id"])),
                measurement_status=MeasurementStatus(str(record["measurement_status"])),
                data_revision=DataRevision(str(record["data_revision"])),
            )
        )
    return tuple(rows)


def frame_from_measurements(measurements: Sequence[Measurement]) -> pd.DataFrame:
    """Serialise domain measurements back to the zone column layout."""
    records = [
        {
            "measurement_id": str(item.measurement_id),
            "timestamp": item.timestamp,
            "lot_id": str(item.lot_id),
            "wafer_id": str(item.wafer_id),
            "slot": item.slot,
            "site_id": int(item.site_id),
            "site_x": item.site_x_mm,
            "site_y": item.site_y_mm,
            "parameter_id": str(item.parameter_id),
            "value": item.value,
            "unit": str(item.unit),
            "step_id": str(item.step_id),
            "tool_id": str(item.tool_id),
            "chamber_id": str(item.chamber_id),
            "recipe_id": str(item.recipe_id),
            "product_id": str(item.product_id),
            "metrology_tool_id": str(item.metrology_tool_id),
            "measurement_status": item.measurement_status.value,
            "data_revision": str(item.data_revision),
        }
        for item in measurements
    ]
    return pd.DataFrame.from_records(records)
