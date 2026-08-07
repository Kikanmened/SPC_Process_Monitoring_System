"""Line overview ordered by what needs attention (NFR-U01)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.domain.enums import ViolationSeverity
from spc_platform.domain.ids import ParameterId


class AttentionRow(BaseModel):
    """One parameter's attention summary for the line overview."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    open_violations: int = Field(ge=0)
    highest_severity: ViolationSeverity | None = None
    has_active_baseline: bool
    attention_rank: int = Field(ge=0)


class LineOverview(BaseModel):
    """Parameters ordered so the worst problems surface first."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: tuple[AttentionRow, ...] = Field(default_factory=tuple)
    n_parameters: int = Field(ge=0)
    n_open_violations: int = Field(ge=0)
