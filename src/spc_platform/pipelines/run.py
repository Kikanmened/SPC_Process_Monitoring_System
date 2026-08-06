"""Composition helper: ingest a raw frame and publish the processed result.

Wired by scripts and tests. Adapters are injected; this module never imports
``infrastructure/``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from spc_platform.application.ports.measurement_repository import MeasurementRepository
from spc_platform.common.time import Clock
from spc_platform.common.units import UnitRegistry
from spc_platform.domain.ids import DataRevision
from spc_platform.domain.lineage import IngestionRunRecord
from spc_platform.pipelines.ingest.stage import IngestionResult, ingest_batch
from spc_platform.pipelines.paths import PipelinePaths
from spc_platform.pipelines.transform.normalise_units import ParameterUnitTarget
from spc_platform.pipelines.transform.pipeline import (
    ProcessingRequest,
    ProcessingResult,
    process_interim,
)
from spc_platform.pipelines.transform.publish import PublishResult


@dataclass(frozen=True, slots=True)
class PipelineRunResult:
    """Full raw-to-processed outcome for one batch."""

    ingestion: IngestionResult
    processing: ProcessingResult

    @property
    def data_revision(self) -> DataRevision:
        """Revision shared by interim and processed rows."""
        return self.ingestion.data_revision

    @property
    def run(self) -> IngestionRunRecord:
        """Ingestion run record for lineage."""
        return self.ingestion.run

    @property
    def publish(self) -> PublishResult:
        """Processed-zone publish outcome."""
        return self.processing.publish


@dataclass(frozen=True, slots=True)
class PipelineDependencies:
    """Injected collaborators for a pipeline run."""

    clock: Clock
    registry: UnitRegistry
    paths: PipelinePaths
    repository: MeasurementRepository | None = None
    unit_targets: Sequence[ParameterUnitTarget] = ()


def run_pipeline(
    frame: pd.DataFrame,
    *,
    source_identity: str,
    dependencies: PipelineDependencies,
) -> PipelineRunResult:
    """Validate, transform, and publish one batch.

    On ingest failure the batch is quarantined and the typed exception
    propagates — nothing is written to interim or processed.
    """
    ingestion = ingest_batch(
        frame,
        source_identity=source_identity,
        clock=dependencies.clock,
        paths=dependencies.paths,
    )
    processing = process_interim(
        ingestion.frame,
        ProcessingRequest(
            data_revision=ingestion.data_revision,
            source_identity=source_identity,
            run_id=ingestion.run.run_id,
            registry=dependencies.registry,
            unit_targets=dependencies.unit_targets,
            processed_directory=dependencies.paths.processed_directory,
            repository=dependencies.repository,
        ),
    )
    return PipelineRunResult(ingestion=ingestion, processing=processing)
