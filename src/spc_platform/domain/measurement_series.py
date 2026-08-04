"""An ordered series of measurements for one parameter.

The analysis-ready handoff from preprocessing to the SPC engine. Values are
extracted as a tuple so analytics never sees a DataFrame.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spc_platform.domain._time import require_aware
from spc_platform.domain.errors import DomainInvariantError
from spc_platform.domain.ids import DataRevision, ParameterId, UnitSymbol
from spc_platform.domain.measurement import Measurement


class MeasurementSeries(BaseModel):
    """Time-ordered measurements of one parameter in one unit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    unit: UnitSymbol
    data_revision: DataRevision
    window_start: datetime
    window_end: datetime
    measurements: tuple[Measurement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _invariants(self) -> MeasurementSeries:
        require_aware(self.window_start, field_name="window_start")
        require_aware(self.window_end, field_name="window_end")
        if self.window_end <= self.window_start:
            raise DomainInvariantError(
                "window_end must be after window_start",
                window_start=str(self.window_start),
                window_end=str(self.window_end),
            )
        previous: datetime | None = None
        for measurement in self.measurements:
            if measurement.parameter_id != self.parameter_id:
                raise DomainInvariantError(
                    "series parameter_id mismatch",
                    series=str(self.parameter_id),
                    measurement=str(measurement.parameter_id),
                )
            if measurement.unit != self.unit:
                raise DomainInvariantError(
                    "series unit mismatch",
                    series_unit=str(self.unit),
                    measurement_unit=str(measurement.unit),
                )
            if previous is not None and measurement.timestamp < previous:
                raise DomainInvariantError(
                    "measurements must be time-ordered",
                    previous=str(previous),
                    current=str(measurement.timestamp),
                )
            previous = measurement.timestamp
        return self

    def values(self) -> tuple[float, ...]:
        """Return the measured values in time order."""
        return tuple(item.value for item in self.measurements)
