"""Mark superseded re-measurements without deleting them (FR-D05)."""

from __future__ import annotations

import numpy as np

from spc_platform.common.errors import AmbiguousRemeasurementError
from spc_platform.domain.enums import MeasurementStatus
from spc_platform.pipelines.stage import StageFrame, StageResult

_STAGE_NAME = "resolve_remeasurements"

_REMEASURE_KEY = (
    "lot_id",
    "wafer_id",
    "site_id",
    "parameter_id",
    "metrology_tool_id",
)


class ResolveRemeasurements:
    """Promote earlier rows to ``superseded`` when a later measurement exists."""

    name = _STAGE_NAME

    def apply(self, stage_frame: StageFrame) -> StageResult:
        """Resolve re-measurements; never drop a row."""
        frame = stage_frame.frame.copy().reset_index(drop=True)
        rows_in = len(frame)
        if frame.empty:
            return StageResult(frame=stage_frame, rows_in=0, rows_out=0)

        ordered = frame.sort_values(
            [*_REMEASURE_KEY, "timestamp", "measurement_id"],
            kind="mergesort",
        ).reset_index(drop=True)

        duplicate_times = ordered.duplicated(
            subset=[*_REMEASURE_KEY, "timestamp"],
            keep=False,
        )
        if bool(duplicate_times.any()):
            sample = ordered.loc[duplicate_times, [*_REMEASURE_KEY, "timestamp"]].head(3)
            raise AmbiguousRemeasurementError(
                "two records share a key and timestamp with no resolvable order",
                sample=sample.to_dict(orient="records"),
            )

        grouped = ordered.groupby(list(_REMEASURE_KEY), sort=False)
        group_sizes = grouped["measurement_id"].transform("size")
        position = grouped.cumcount()
        is_last = position == (group_sizes - 1)
        multi = group_sizes > 1

        statuses = ordered["measurement_status"].astype(str).to_numpy().copy()
        superseded = (multi & ~is_last).to_numpy()
        survivor = (multi & is_last).to_numpy()
        statuses[superseded] = MeasurementStatus.SUPERSEDED.value
        statuses[survivor] = MeasurementStatus.REMEASURED.value
        ordered["measurement_status"] = statuses

        n_superseded = int(np.count_nonzero(superseded))
        note = f"superseded={n_superseded}"
        outgoing = StageFrame(
            frame=ordered,
            context=stage_frame.context,
            notes=(*stage_frame.notes, note),
        )
        return StageResult(
            frame=outgoing,
            rows_in=rows_in,
            rows_out=len(ordered),
            transformations=(note,) if n_superseded else (),
        )
