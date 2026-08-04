"""MeasurementSeries ordering and consistency invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tests.factories.domain import a_measurement, aware

from spc_platform.domain import (
    DataRevision,
    DomainInvariantError,
    MeasurementSeries,
    ParameterId,
    UnitSymbol,
)


@pytest.mark.unit
def test_series_rejects_out_of_order_timestamps() -> None:
    earlier = a_measurement(timestamp=aware(day=2))
    later = a_measurement(timestamp=aware(day=1))
    with pytest.raises((ValidationError, DomainInvariantError)):
        MeasurementSeries(
            parameter_id=ParameterId("OXIDE_THK"),
            unit=UnitSymbol("nm"),
            data_revision=DataRevision("rev-1"),
            window_start=aware(day=1),
            window_end=aware(day=3),
            measurements=(earlier, later),
        )


@pytest.mark.unit
def test_series_values_are_time_ordered() -> None:
    m1 = a_measurement(timestamp=aware(day=1), value=10.0)
    m2 = a_measurement(timestamp=aware(day=2), value=10.2)
    series = MeasurementSeries(
        parameter_id=ParameterId("OXIDE_THK"),
        unit=UnitSymbol("nm"),
        data_revision=DataRevision("rev-1"),
        window_start=aware(day=1),
        window_end=aware(day=3),
        measurements=(m1, m2),
    )
    assert series.values() == (10.0, 10.2)
