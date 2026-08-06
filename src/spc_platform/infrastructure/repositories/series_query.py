"""Shared filtering for measurement series queries across adapters."""

from __future__ import annotations

from collections.abc import Sequence

from spc_platform.application.ports.measurement_repository import SeriesQuery, WaferQuery
from spc_platform.common.errors import InsufficientDataError
from spc_platform.domain.enums import MeasurementStatus
from spc_platform.domain.ids import DataRevision
from spc_platform.domain.measurement import Measurement
from spc_platform.domain.measurement_series import MeasurementSeries


def is_chartable(item: Measurement) -> bool:
    """Return whether the measurement participates in charting queries.

    Superseded rows remain stored (FR-D05) but must not double-count a site.
    """
    return item.measurement_status is not MeasurementStatus.SUPERSEDED


def filter_series(
    measurements: Sequence[Measurement],
    query: SeriesQuery,
) -> tuple[Measurement, ...]:
    """Apply ``SeriesQuery`` filters and return time-ordered chartable rows."""
    matched = [
        item
        for item in measurements
        if is_chartable(item)
        and item.parameter_id == query.parameter_id
        and query.window_start <= item.timestamp <= query.window_end
        and (query.product_id is None or item.product_id == query.product_id)
        and (query.lot_id is None or item.lot_id == query.lot_id)
        and (query.data_revision is None or item.data_revision == query.data_revision)
    ]
    matched.sort(key=lambda item: (item.timestamp, str(item.measurement_id)))
    return tuple(matched)


def filter_sites(
    measurements: Sequence[Measurement],
    query: WaferQuery,
) -> tuple[Measurement, ...]:
    """Apply ``WaferQuery`` filters and return site_id-ordered chartable rows."""
    matched = [
        item
        for item in measurements
        if is_chartable(item)
        and item.parameter_id == query.parameter_id
        and item.lot_id == query.lot_id
        and item.wafer_id == query.wafer_id
        and (query.data_revision is None or item.data_revision == query.data_revision)
    ]
    matched.sort(key=lambda item: (int(item.site_id), str(item.measurement_id)))
    return tuple(matched)


def series_from_measurements(
    query: SeriesQuery,
    measurements: Sequence[Measurement],
) -> MeasurementSeries:
    """Build a ``MeasurementSeries`` or raise when nothing matched."""
    ordered = filter_series(measurements, query)
    if not ordered:
        raise InsufficientDataError(
            "no measurements match the series query",
            parameter_id=str(query.parameter_id),
            window_start=str(query.window_start),
            window_end=str(query.window_end),
        )
    units = {item.unit for item in ordered}
    if len(units) != 1:
        raise InsufficientDataError(
            "series query matched measurements in more than one unit",
            units=sorted(str(unit) for unit in units),
        )
    revisions = {item.data_revision for item in ordered}
    revision: DataRevision
    if query.data_revision is not None:
        revision = query.data_revision
    elif len(revisions) == 1:
        revision = next(iter(revisions))
    else:
        # Mixed revisions in one window are still a valid series for charting
        # when the caller did not pin a revision; stamp the latest by timestamp.
        revision = ordered[-1].data_revision
    unit = next(iter(units))
    return MeasurementSeries(
        parameter_id=query.parameter_id,
        unit=unit,
        data_revision=revision,
        window_start=query.window_start,
        window_end=query.window_end,
        measurements=ordered,
    )
