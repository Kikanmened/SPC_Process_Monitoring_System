"""Pipeline lineage: the data revision and the run that produced it (FR-D09)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from spc_platform.domain._time import require_aware
from spc_platform.domain.ids import DataRevision


class IngestionRunRecord(BaseModel):
    """One attempt to admit a raw batch into the interim zone.

    Attributes
    ----------
    run_id
        Stable identity of this attempt. Distinct even when the same batch is
        re-ingested (NFR-R01 records each run; rows are not duplicated).
    source_identity
        What was read — path, dataset id, or adapter name.
    data_revision
        Revision assigned to every admitted row. Derived from batch content so
        re-ingesting the same bytes yields the same revision.
    rows_in, rows_out
        Counts at the boundary. Equal on success; on failure the run never
        reaches a record with ``succeeded=True``.
    started_at, finished_at
        Wall times from the injected clock.
    succeeded
        False when the batch was quarantined. A failed run leaves no interim
        rows for its revision.
    validation_summary
        Short human-readable outcome for the run log.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str = Field(min_length=1)
    source_identity: str = Field(min_length=1)
    data_revision: DataRevision
    rows_in: int = Field(ge=0)
    rows_out: int = Field(ge=0)
    started_at: datetime
    finished_at: datetime
    succeeded: bool
    validation_summary: str = ""

    @field_validator("started_at", "finished_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return require_aware(value, field_name="timestamp")
