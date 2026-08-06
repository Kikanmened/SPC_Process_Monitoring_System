"""Admit one raw batch into the interim zone, or fail with quarantine."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from spc_platform.common.errors import (
    DuplicateMeasurementKeyError,
    NaiveDatetimeError,
    SchemaValidationError,
)
from spc_platform.common.time import Clock
from spc_platform.domain.ids import DataRevision
from spc_platform.domain.lineage import IngestionRunRecord
from spc_platform.pipelines.ingest.keys import (
    DEFAULT_MEASUREMENT_KEY,
    require_unique_keys,
)
from spc_platform.pipelines.ingest.quarantine import QuarantineArtefact, quarantine_batch
from spc_platform.pipelines.ingest.validation import validate_raw_batch
from spc_platform.pipelines.lineage import (
    assign_data_revision,
    build_run_record,
    data_revision_for,
    new_run_id,
)
from spc_platform.pipelines.paths import PipelinePaths
from spc_platform.pipelines.schemas.measurement import InterimMeasurementSchema


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Successful admission of a raw batch."""

    frame: pd.DataFrame
    data_revision: DataRevision
    run: IngestionRunRecord
    interim_path: Path | None


def _write_interim(frame: pd.DataFrame, directory: Path, revision: DataRevision) -> Path:
    """Atomically write the interim Parquet for this revision."""
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{revision}.parquet"
    temporary = directory / f".{revision}.parquet.tmp"
    frame.to_parquet(temporary, index=False)
    temporary.replace(target)
    return target


def ingest_batch(
    frame: pd.DataFrame,
    *,
    source_identity: str,
    clock: Clock,
    paths: PipelinePaths,
    key_columns: Sequence[str] = DEFAULT_MEASUREMENT_KEY,
) -> IngestionResult:
    """Validate and admit one batch, or raise without writing interim data.

    On schema, timestamp, or key failure the batch is quarantined and the
    corresponding typed exception is raised. Nothing is written under
    ``paths.interim_directory`` in that case.
    """
    run_id = new_run_id()
    started = clock.now()
    rows_in = len(frame)
    revision = data_revision_for(frame)

    try:
        validate_raw_batch(frame)
        require_unique_keys(frame, key_columns)
    except (SchemaValidationError, NaiveDatetimeError, DuplicateMeasurementKeyError) as exc:
        artefact = _quarantine_failure(
            frame,
            _QuarantineRequest(
                quarantine_root=paths.quarantine_root,
                run_id=run_id,
                revision=revision,
                source_identity=source_identity,
                error=exc,
                rows_in=rows_in,
            ),
        )
        finished = clock.now()
        _ = build_run_record(
            run_id=run_id,
            source_identity=source_identity,
            data_revision=revision,
            rows_in=rows_in,
            rows_out=0,
            started_at=started,
            finished_at=finished,
            succeeded=False,
            validation_summary=str(exc),
        )
        exc.context["quarantine"] = str(artefact.directory)
        exc.context["run_id"] = run_id
        raise

    admitted = assign_data_revision(frame, revision)
    InterimMeasurementSchema.validate(admitted)
    interim_path = None
    if paths.interim_directory is not None:
        interim_path = _write_interim(admitted, paths.interim_directory, revision)

    finished = clock.now()
    run = build_run_record(
        run_id=run_id,
        source_identity=source_identity,
        data_revision=revision,
        rows_in=rows_in,
        rows_out=len(admitted),
        started_at=started,
        finished_at=finished,
        succeeded=True,
        validation_summary=f"admitted {len(admitted)} rows",
    )
    return IngestionResult(
        frame=admitted,
        data_revision=revision,
        run=run,
        interim_path=interim_path,
    )


@dataclass(frozen=True, slots=True)
class _QuarantineRequest:
    quarantine_root: Path
    run_id: str
    revision: DataRevision
    source_identity: str
    error: Exception
    rows_in: int


def _quarantine_failure(
    frame: pd.DataFrame,
    request: _QuarantineRequest,
) -> QuarantineArtefact:
    """Persist the rejected batch and a machine-readable report."""
    report: dict[str, object] = {
        "run_id": request.run_id,
        "source_identity": request.source_identity,
        "data_revision": str(request.revision),
        "rows_in": request.rows_in,
        "error_type": type(request.error).__name__,
        "error_message": str(request.error),
        "error_context": getattr(request.error, "context", {}),
    }
    return quarantine_batch(
        frame,
        quarantine_root=request.quarantine_root,
        run_id=request.run_id,
        report=report,
    )
