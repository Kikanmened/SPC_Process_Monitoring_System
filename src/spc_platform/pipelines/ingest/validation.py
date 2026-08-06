"""Raw-zone schema application as a hard stop (FR-D02, FR-D03)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pandera.errors as pa_errors

from spc_platform.common.errors import NaiveDatetimeError, SchemaValidationError
from spc_platform.pipelines.schemas.measurement import RawMeasurementSchema


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Structured failure detail for a quarantined batch."""

    schema_name: str
    failure_cases: tuple[str, ...]
    row_count: int

    def summary(self) -> str:
        """One-line outcome for the run record."""
        if not self.failure_cases:
            return f"{self.schema_name}: ok ({self.row_count} rows)"
        head = self.failure_cases[0]
        extra = len(self.failure_cases) - 1
        if extra <= 0:
            return f"{self.schema_name}: {head}"
        return f"{self.schema_name}: {head} (+{extra} more)"


def _naive_timestamp_count(frame: pd.DataFrame) -> int:
    """Count timestamps that lack timezone information."""
    if "timestamp" not in frame.columns:
        return 0
    series = frame["timestamp"]
    if not pd.api.types.is_datetime64_any_dtype(series):
        # String timestamps are left to Pandera; naive check applies to datetimes.
        try:
            parsed = pd.to_datetime(series, utc=False)
        except (TypeError, ValueError):
            return 0
        series = parsed
    if getattr(series.dtype, "tz", None) is not None:
        return 0
    # datetime64[ns] without tz — every non-null value is naive.
    return int(series.notna().sum())


def validate_raw_batch(frame: pd.DataFrame) -> ValidationReport:
    """Validate against the raw-zone schema, or raise without mutating state.

    Raises
    ------
    NaiveDatetimeError
        If any timestamp is timezone-naive (FR-D04).
    SchemaValidationError
        If any record fails the raw-zone schema.
    """
    naive = _naive_timestamp_count(frame)
    if naive:
        raise NaiveDatetimeError(
            "raw batch contains timezone-naive timestamps",
            field_name="timestamp",
            row_count=naive,
        )
    try:
        RawMeasurementSchema.validate(frame, lazy=True)
    except pa_errors.SchemaErrors as exc:
        cases = tuple(str(failure) for failure in exc.failure_cases.head(20).itertuples())
        report = ValidationReport(
            schema_name=RawMeasurementSchema.name or "raw_measurement",
            failure_cases=cases or (str(exc),),
            row_count=len(frame),
        )
        raise SchemaValidationError(
            "raw batch failed schema validation",
            schema=report.schema_name,
            failure_count=len(exc.failure_cases),
            summary=report.summary(),
        ) from exc
    return ValidationReport(
        schema_name=RawMeasurementSchema.name or "raw_measurement",
        failure_cases=(),
        row_count=len(frame),
    )
