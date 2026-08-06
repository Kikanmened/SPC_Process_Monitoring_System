"""Read/write port over the processed measurement zone (Module 2)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from spc_platform.domain.ids import (
    DataRevision,
    LotId,
    ParameterId,
    ProductId,
    WaferId,
)
from spc_platform.domain.measurement import Measurement
from spc_platform.domain.measurement_series import MeasurementSeries


@dataclass(frozen=True, slots=True)
class SeriesQuery:
    """Select a time-ordered series of one parameter for charting."""

    parameter_id: ParameterId
    window_start: datetime
    window_end: datetime
    product_id: ProductId | None = None
    lot_id: LotId | None = None
    data_revision: DataRevision | None = None


@dataclass(frozen=True, slots=True)
class WaferQuery:
    """Select every site measurement on one wafer for one parameter."""

    parameter_id: ParameterId
    lot_id: LotId
    wafer_id: WaferId
    data_revision: DataRevision | None = None


class MeasurementRepository(Protocol):
    """Processed-zone persistence. DuckDB, PostgreSQL, and the fake implement this.

    Analytics never sees a DataFrame: callers receive ``Measurement`` /
    ``MeasurementSeries`` value objects.
    """

    def replace_revision(
        self,
        revision: DataRevision,
        measurements: Sequence[Measurement],
    ) -> None:
        """Replace all rows for ``revision`` with ``measurements`` atomically.

        Re-publishing the same revision is idempotent (NFR-R01): the prior rows
        for that revision are removed and the new set is written in one step.
        """
        ...

    def series_for(self, query: SeriesQuery) -> MeasurementSeries:
        """Return the matching series, time-ordered.

        Raises
        ------
        InsufficientDataError
            If no measurements match the query.
        """
        ...

    def sites_for(self, query: WaferQuery) -> tuple[Measurement, ...]:
        """Return every site on the wafer for the parameter, site_id ordered."""
        ...

    def has_revision(self, revision: DataRevision) -> bool:
        """Return whether any row carries ``revision``."""
        ...
