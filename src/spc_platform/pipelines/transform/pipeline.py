"""Run the transform stages from interim to processed."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from spc_platform.application.ports.measurement_repository import MeasurementRepository
from spc_platform.common.units import UnitRegistry
from spc_platform.domain.ids import DataRevision
from spc_platform.pipelines.stage import StageContext, StageFrame, StageResult
from spc_platform.pipelines.transform.attach_context import AttachContext
from spc_platform.pipelines.transform.normalise_units import (
    NormaliseUnits,
    ParameterUnitTarget,
)
from spc_platform.pipelines.transform.publish import PublishProcessed, PublishResult
from spc_platform.pipelines.transform.resolve_remeasurements import ResolveRemeasurements


@dataclass(frozen=True, slots=True)
class ProcessingRequest:
    """Inputs for the transform pipeline beyond the interim frame."""

    data_revision: DataRevision
    source_identity: str
    run_id: str
    registry: UnitRegistry
    unit_targets: Sequence[ParameterUnitTarget] = ()
    processed_directory: Path | None = None
    repository: MeasurementRepository | None = None


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    """Outcome of running the full transform pipeline."""

    frame: pd.DataFrame
    data_revision: DataRevision
    publish: PublishResult
    stage_results: tuple[StageResult, ...]


def process_interim(
    frame: pd.DataFrame,
    request: ProcessingRequest,
) -> ProcessingResult:
    """Resolve re-measurements, normalise units, and publish.

    Subgrouping collapses site grain into chart points and runs at the series
    boundary via ``build_subgroups`` — the processed zone keeps every site row.
    Outlier flagging records a rule identity when a policy is supplied; the
    default path does not invent flags.
    """
    context = StageContext(
        data_revision=request.data_revision,
        source_identity=request.source_identity,
        run_id=request.run_id,
    )
    current = StageFrame(frame=frame, context=context)
    stages = (
        AttachContext(),
        ResolveRemeasurements(),
        NormaliseUnits(request.registry, tuple(request.unit_targets)),
    )
    results: list[StageResult] = []
    for stage in stages:
        outcome = stage.apply(current)
        results.append(outcome)
        current = outcome.frame

    publisher = PublishProcessed(
        processed_directory=request.processed_directory,
        repository=request.repository,
    )
    published = publisher.publish(current)
    results.append(published.stage)
    return ProcessingResult(
        frame=published.stage.frame.frame,
        data_revision=request.data_revision,
        publish=published,
        stage_results=tuple(results),
    )
