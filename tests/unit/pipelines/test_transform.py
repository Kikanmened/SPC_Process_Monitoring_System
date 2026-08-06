"""Transform stages: re-measurements, units, publish, subgrouping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest
from tests.factories.domain import a_measurement, aware
from tests.factories.frames import a_raw_frame, a_raw_row

from spc_platform.common.errors import AmbiguousRemeasurementError, UnitConversionError
from spc_platform.common.units import UnitConversion, UnitRegistry
from spc_platform.domain.enums import MeasurementStatus, SubgroupingKind
from spc_platform.domain.ids import DataRevision, MeasurementId, ParameterId, UnitSymbol
from spc_platform.domain.measurement_series import MeasurementSeries
from spc_platform.domain.subgrouping import SubgroupingStrategy
from spc_platform.infrastructure.repositories.fake import FakeMeasurementRepository
from spc_platform.pipelines.mapping import measurements_from_frame
from spc_platform.pipelines.stage import StageContext, StageFrame
from spc_platform.pipelines.transform import (
    ParameterUnitTarget,
    ProcessingRequest,
    ResolveRemeasurements,
    build_subgroups,
    process_interim,
)


def _stage_frame(frame: pd.DataFrame) -> StageFrame:
    return StageFrame(
        frame=frame,
        context=StageContext(
            data_revision=DataRevision("dr-test"),
            source_identity="test",
            run_id="run-test",
        ),
    )


@pytest.mark.unit
def test_resolve_remeasurements_marks_earlier_superseded() -> None:
    earlier = a_raw_row(
        measurement_id=str(uuid4()),
        timestamp=datetime(2025, 6, 1, 12, 0, tzinfo=UTC),
        value=10.0,
        measurement_status="valid",
    )
    later = a_raw_row(
        measurement_id=str(uuid4()),
        timestamp=datetime(2025, 6, 1, 13, 0, tzinfo=UTC),
        value=10.1,
        measurement_status="valid",
    )
    frame = a_raw_frame(earlier, later)
    frame["data_revision"] = "dr-test"
    result = ResolveRemeasurements().apply(_stage_frame(frame))
    statuses = set(result.frame.frame["measurement_status"].tolist())
    assert statuses == {"superseded", "remeasured"}
    assert result.rows_out == 2


@pytest.mark.unit
def test_ambiguous_remeasurement_same_timestamp_raises() -> None:
    shared = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)
    first = a_raw_row(measurement_id=str(uuid4()), timestamp=shared, value=10.0)
    second = a_raw_row(measurement_id=str(uuid4()), timestamp=shared, value=10.1)
    frame = a_raw_frame(first, second)
    frame["data_revision"] = "dr-test"
    with pytest.raises(AmbiguousRemeasurementError):
        ResolveRemeasurements().apply(_stage_frame(frame))


@pytest.mark.unit
def test_normalise_units_converts_when_declared(tmp_path: Path) -> None:
    registry = UnitRegistry(
        units=frozenset({UnitSymbol("nm"), UnitSymbol("angstrom")}),
        conversions=(
            UnitConversion(
                source=UnitSymbol("angstrom"),
                target=UnitSymbol("nm"),
                factor=0.1,
            ),
        ),
    )
    frame = a_raw_frame(a_raw_row(unit="angstrom", value=100.0))
    frame["data_revision"] = "dr-test"
    repository = FakeMeasurementRepository()
    result = process_interim(
        frame,
        ProcessingRequest(
            data_revision=DataRevision("dr-test"),
            source_identity="test",
            run_id="run-test",
            registry=registry,
            unit_targets=(ParameterUnitTarget(ParameterId("OXIDE_THK"), UnitSymbol("nm")),),
            processed_directory=tmp_path / "processed",
            repository=repository,
        ),
    )
    assert result.frame.loc[0, "unit"] == "nm"
    assert result.frame.loc[0, "value"] == pytest.approx(10.0)
    assert repository.has_revision(DataRevision("dr-test"))


@pytest.mark.unit
def test_undeclared_unit_conversion_raises() -> None:
    registry = UnitRegistry(
        units=frozenset({UnitSymbol("nm"), UnitSymbol("um")}),
        conversions=(),
    )
    frame = a_raw_frame(a_raw_row(unit="um", value=0.01))
    frame["data_revision"] = "dr-test"
    with pytest.raises(UnitConversionError):
        process_interim(
            frame,
            ProcessingRequest(
                data_revision=DataRevision("dr-test"),
                source_identity="test",
                run_id="run-test",
                registry=registry,
                unit_targets=(ParameterUnitTarget(ParameterId("OXIDE_THK"), UnitSymbol("nm")),),
            ),
        )


@pytest.mark.unit
def test_mapping_round_trip_preserves_site_coordinates() -> None:
    frame = a_raw_frame(a_raw_row(site_x=12.5, site_y=-3.0))
    frame["data_revision"] = "dr-test"
    measurements = measurements_from_frame(frame)
    assert measurements[0].site_x_mm == 12.5
    assert measurements[0].site_y_mm == -3.0


@pytest.mark.unit
def test_build_subgroups_wafer_mean_excludes_superseded() -> None:
    m1 = a_measurement(
        timestamp=aware(day=1),
        value=10.0,
        measurement_status=MeasurementStatus.SUPERSEDED,
        site_id=1,
    )
    m2 = a_measurement(
        timestamp=aware(day=1) + timedelta(hours=1),
        value=12.0,
        measurement_status=MeasurementStatus.REMEASURED,
        site_id=1,
        measurement_id=MeasurementId(uuid4()),
    )
    series = MeasurementSeries(
        parameter_id=m1.parameter_id,
        unit=m1.unit,
        data_revision=m1.data_revision,
        window_start=aware(day=1),
        window_end=aware(day=2),
        measurements=(m1, m2),
    )
    subgroups = build_subgroups(
        series,
        SubgroupingStrategy(kind=SubgroupingKind.WAFER_MEAN),
    )
    assert len(subgroups) == 1
    assert subgroups[0].values == (12.0,)
