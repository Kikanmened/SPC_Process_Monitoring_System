"""Assign data revisions and build ingestion run records (FR-D09)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import uuid4

import pandas as pd

from spc_platform.domain.ids import DataRevision
from spc_platform.domain.lineage import IngestionRunRecord

_DIGEST_BYTES = 16


def new_run_id() -> str:
    """Return a unique run identifier."""
    return f"run-{uuid4().hex}"


def data_revision_for(frame: pd.DataFrame) -> DataRevision:
    """Derive a content-addressed revision from the batch values.

    The same bytes produce the same revision, which is what makes re-ingestion
    idempotent at the row level (NFR-R01): a second run records a new attempt
    but writes the same revision, and ``replace_revision`` replaces rather than
    duplicates.
    """
    digest = hashlib.blake2b(digest_size=_DIGEST_BYTES)
    columns = list(frame.columns)
    digest.update(json.dumps(columns, separators=(",", ":")).encode("utf-8"))
    for column in columns:
        series = frame[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            values = pd.to_datetime(series, utc=True).astype("int64").to_numpy().tobytes()
            digest.update(values)
        elif pd.api.types.is_numeric_dtype(series):
            digest.update(series.astype("float64").to_numpy().tobytes())
        else:
            for value in series.astype(str).tolist():
                digest.update(value.encode("utf-8"))
                digest.update(b"\x00")
    return DataRevision(f"dr-{digest.hexdigest()}")


def assign_data_revision(frame: pd.DataFrame, revision: DataRevision) -> pd.DataFrame:
    """Return a copy of ``frame`` with ``data_revision`` set on every row."""
    assigned = frame.copy()
    assigned["data_revision"] = str(revision)
    return assigned


def build_run_record(  # noqa: PLR0913 — mirrors IngestionRunRecord fields
    *,
    run_id: str,
    source_identity: str,
    data_revision: DataRevision,
    rows_in: int,
    rows_out: int,
    started_at: datetime,
    finished_at: datetime,
    succeeded: bool,
    validation_summary: str,
) -> IngestionRunRecord:
    """Assemble an immutable run record for the lineage store."""
    return IngestionRunRecord(
        run_id=run_id,
        source_identity=source_identity,
        data_revision=data_revision,
        rows_in=rows_in,
        rows_out=rows_out,
        started_at=started_at,
        finished_at=finished_at,
        succeeded=succeeded,
        validation_summary=validation_summary,
    )
