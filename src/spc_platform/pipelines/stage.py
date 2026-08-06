"""Shared stage protocol for the transform pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd

from spc_platform.domain.ids import DataRevision


@dataclass(frozen=True, slots=True)
class StageContext:
    """Cross-stage context that travels with a batch through the pipeline."""

    data_revision: DataRevision
    source_identity: str
    run_id: str


@dataclass(slots=True)
class StageFrame:
    """Tabular batch at a pipeline boundary.

    Mutable only in the sense that a stage returns a new frame; callers must
    not mutate ``frame`` after construction.
    """

    frame: pd.DataFrame
    context: StageContext
    notes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StageResult:
    """Outcome of one stage: the outgoing frame and what changed."""

    frame: StageFrame
    rows_in: int
    rows_out: int
    transformations: tuple[str, ...] = field(default_factory=tuple)


class PipelineStage(Protocol):
    """One named, independently testable transformation with lineage."""

    name: str

    def apply(self, stage_frame: StageFrame) -> StageResult:
        """Transform the frame, or raise without side effects."""
        ...
