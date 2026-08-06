"""In-memory measurement repository and baseline store for tests."""

from __future__ import annotations

from collections.abc import Sequence

from spc_platform.application.ports.measurement_repository import SeriesQuery, WaferQuery
from spc_platform.domain.baseline import Baseline
from spc_platform.domain.enums import BaselineStatus
from spc_platform.domain.ids import BaselineId, DataRevision, ParameterId
from spc_platform.domain.measurement import Measurement
from spc_platform.domain.measurement_series import MeasurementSeries
from spc_platform.infrastructure.repositories.series_query import (
    filter_sites,
    series_from_measurements,
)


class FakeMeasurementRepository:
    """Dict-backed ``MeasurementRepository`` for unit and contract tests."""

    def __init__(self) -> None:
        self._by_revision: dict[DataRevision, tuple[Measurement, ...]] = {}

    def replace_revision(
        self,
        revision: DataRevision,
        measurements: Sequence[Measurement],
    ) -> None:
        """Replace all rows for ``revision`` atomically."""
        for item in measurements:
            if item.data_revision != revision:
                message = "measurement data_revision must match replace_revision argument"
                raise ValueError(message)
        self._by_revision[revision] = tuple(measurements)

    def series_for(self, query: SeriesQuery) -> MeasurementSeries:
        """Return the matching series, time-ordered."""
        return series_from_measurements(query, self._all())

    def sites_for(self, query: WaferQuery) -> tuple[Measurement, ...]:
        """Return every chartable site on the wafer for the parameter."""
        return filter_sites(self._all(), query)

    def has_revision(self, revision: DataRevision) -> bool:
        """Return whether any row carries ``revision``."""
        return revision in self._by_revision and bool(self._by_revision[revision])

    def _all(self) -> tuple[Measurement, ...]:
        rows: list[Measurement] = []
        for batch in self._by_revision.values():
            rows.extend(batch)
        return tuple(rows)


class FakeBaselineStore:
    """Dict-backed ``BaselineStore`` with activation supersession."""

    def __init__(self) -> None:
        self._items: dict[BaselineId, Baseline] = {}

    def get(self, baseline_id: BaselineId) -> Baseline | None:
        """Return the baseline, or None if unknown."""
        return self._items.get(baseline_id)

    def active_for(self, parameter_id: ParameterId) -> Baseline | None:
        """Return the active baseline for the parameter, if any."""
        for baseline in self._items.values():
            if baseline.parameter_id == parameter_id and baseline.status is BaselineStatus.ACTIVE:
                return baseline
        return None

    def save(self, baseline: Baseline) -> None:
        """Store a baseline; activating one supersedes the previous active."""
        if baseline.baseline_id in self._items:
            message = "baselines are immutable once saved"
            raise ValueError(message)

        if baseline.status is BaselineStatus.ACTIVE:
            previous = self.active_for(baseline.parameter_id)
            if previous is not None:
                self._items[previous.baseline_id] = previous.model_copy(
                    update={"status": BaselineStatus.SUPERSEDED}
                )

        self._items[baseline.baseline_id] = baseline

    def list_for(
        self,
        parameter_id: ParameterId,
        *,
        status: BaselineStatus | None = None,
    ) -> tuple[Baseline, ...]:
        """Return baselines for the parameter, newest effective_from first."""
        matched = [
            item
            for item in self._items.values()
            if item.parameter_id == parameter_id and (status is None or item.status is status)
        ]
        matched.sort(key=lambda item: item.effective_from, reverse=True)
        return tuple(matched)
