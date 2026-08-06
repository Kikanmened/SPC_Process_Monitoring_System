"""Confirm process context columns are present (NFR-CO02).

The synthetic and file sources already carry step, tool, chamber, recipe,
product, and metrology tool on every row. This stage is the explicit check so
a future lean export cannot silently drop them.
"""

from __future__ import annotations

from spc_platform.common.errors import SchemaValidationError
from spc_platform.pipelines.stage import StageFrame, StageResult

_STAGE_NAME = "attach_context"

_REQUIRED_CONTEXT = (
    "step_id",
    "tool_id",
    "chamber_id",
    "recipe_id",
    "product_id",
    "metrology_tool_id",
)


class AttachContext:
    """Require context columns; never invent missing values."""

    name = _STAGE_NAME

    def apply(self, stage_frame: StageFrame) -> StageResult:
        """Pass the frame through when every context column is present."""
        frame = stage_frame.frame
        rows_in = len(frame)
        missing = [column for column in _REQUIRED_CONTEXT if column not in frame.columns]
        if missing:
            raise SchemaValidationError(
                "batch is missing required process context columns",
                missing=missing,
            )
        note = "context_present"
        outgoing = StageFrame(
            frame=frame,
            context=stage_frame.context,
            notes=(*stage_frame.notes, note),
        )
        return StageResult(
            frame=outgoing,
            rows_in=rows_in,
            rows_out=rows_in,
            transformations=(note,),
        )
