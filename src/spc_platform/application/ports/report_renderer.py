"""Port for deterministic report rendering (FR-RP01 - FR-RP03)."""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.application.reporting.models import ReportModel
from spc_platform.common.provenance import Provenance
from spc_platform.domain.enums import ReportType


class RenderTarget(StrEnum):
    """Output form for a rendered report."""

    HTML = "html"
    PDF = "pdf"


class ReportArtefact(BaseModel):
    """Bytes of a rendered report with provenance for independent verification."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_type: ReportType
    target: RenderTarget
    media_type: str
    content: bytes
    provenance: Provenance
    parameters: dict[str, str] = Field(default_factory=dict)


class ReportRenderer(Protocol):
    """Render a report model to HTML or PDF without computing statistics."""

    def render(self, report: ReportModel, target: RenderTarget) -> ReportArtefact:
        """Produce an artefact; raise ``ReportRenderError`` on failure."""
        ...
