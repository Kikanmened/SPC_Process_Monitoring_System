"""Atomic publish to the processed zone (NFR-R04)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from spc_platform.application.ports.measurement_repository import MeasurementRepository
from spc_platform.common.errors import PipelinePublishError, SchemaValidationError
from spc_platform.domain.ids import DataRevision
from spc_platform.pipelines.mapping import measurements_from_frame
from spc_platform.pipelines.schemas.measurement import ProcessedMeasurementSchema
from spc_platform.pipelines.stage import StageFrame, StageResult

_STAGE_NAME = "publish"


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Where the processed batch was written and how many rows landed."""

    path: Path | None
    revision: DataRevision
    row_count: int
    stage: StageResult


class PublishProcessed:
    """Validate the processed schema, write Parquet, and upsert the repository."""

    name = _STAGE_NAME

    def __init__(
        self,
        *,
        processed_directory: Path | None = None,
        repository: MeasurementRepository | None = None,
    ) -> None:
        self._directory = processed_directory
        self._repository = repository

    def apply(self, stage_frame: StageFrame) -> StageResult:
        """Publish the frame; used when only the stage protocol is needed."""
        result = self.publish(stage_frame)
        return result.stage

    def publish(self, stage_frame: StageFrame) -> PublishResult:
        """Validate, write, and persist. Failures leave no partial processed file."""
        frame = stage_frame.frame.copy().reset_index(drop=True)
        rows_in = len(frame)
        try:
            ProcessedMeasurementSchema.validate(frame)
        except Exception as exc:
            raise SchemaValidationError(
                "processed batch failed schema validation",
                schema="processed_measurement",
                reason=str(exc),
            ) from exc

        revision = stage_frame.context.data_revision
        path = None
        if self._directory is not None:
            path = self._write_atomic(frame, self._directory, revision)

        if self._repository is not None:
            self._repository.replace_revision(revision, measurements_from_frame(frame))

        note = f"published={rows_in}"
        outgoing = StageFrame(
            frame=frame,
            context=stage_frame.context,
            notes=(*stage_frame.notes, note),
        )
        stage = StageResult(
            frame=outgoing,
            rows_in=rows_in,
            rows_out=rows_in,
            transformations=(note,),
        )
        return PublishResult(
            path=path,
            revision=revision,
            row_count=rows_in,
            stage=stage,
        )

    @staticmethod
    def _write_atomic(frame: pd.DataFrame, directory: Path, revision: DataRevision) -> Path:
        """Write via a temporary file then replace."""
        try:
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / f"{revision}.parquet"
            temporary = directory / f".{revision}.parquet.tmp"
            frame.to_parquet(temporary, index=False)
            temporary.replace(target)
        except OSError as exc:
            raise PipelinePublishError(
                "failed to write processed zone",
                directory=str(directory),
                revision=str(revision),
                reason=str(exc),
            ) from exc
        return target
