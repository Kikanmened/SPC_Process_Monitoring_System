"""Jinja2 HTML rendering with optional WeasyPrint PDF (FR-RP02, FR-RP03)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from jinja2 import Environment, FileSystemLoader, select_autoescape

from spc_platform.application.ports.report_renderer import (
    RenderTarget,
    ReportArtefact,
)
from spc_platform.application.reporting.models import ReportModel
from spc_platform.common.errors import ReportRenderError
from spc_platform.domain.enums import ReportType

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

_TEMPLATE_BY_TYPE: dict[ReportType, str] = {
    ReportType.SPC_SUMMARY: "spc_summary.html.j2",
    ReportType.CAPABILITY_STUDY: "capability_study.html.j2",
    ReportType.MSA_REPORT: "msa_report.html.j2",
    ReportType.EXCURSION_SUMMARY: "excursion_summary.html.j2",
}


class JinjaReportRenderer:
    """Render report models to deterministic HTML; PDF when WeasyPrint is available."""

    def __init__(self, template_dir: Path | None = None) -> None:
        directory = template_dir if template_dir is not None else _TEMPLATE_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(directory)),
            autoescape=select_autoescape(enabled_extensions=("html", "j2")),
            trim_blocks=True,
            lstrip_blocks=True,
            # Keep output stable across runs for FR-RP03.
            keep_trailing_newline=True,
        )

    def render(self, report: ReportModel, target: RenderTarget) -> ReportArtefact:
        """Render HTML always; PDF via WeasyPrint when system libraries allow."""
        html = self._render_html(report)
        if target is RenderTarget.HTML:
            return ReportArtefact(
                report_type=report.report_type,
                target=RenderTarget.HTML,
                media_type="text/html; charset=utf-8",
                content=html.encode("utf-8"),
                provenance=report.provenance,
                parameters=dict(sorted(report.parameters.items())),
            )
        pdf_bytes = self._html_to_pdf(html)
        return ReportArtefact(
            report_type=report.report_type,
            target=RenderTarget.PDF,
            media_type="application/pdf",
            content=pdf_bytes,
            provenance=report.provenance,
            parameters=dict(sorted(report.parameters.items())),
        )

    def _render_html(self, report: ReportModel) -> str:
        template_name = _TEMPLATE_BY_TYPE.get(report.report_type)
        if template_name is None:
            raise ReportRenderError(
                "no template registered for report type",
                report_type=report.report_type.value,
            )
        template = self._env.get_template(template_name)
        # Sorted parameter keys keep regenerations byte-identical.
        context = {
            "title": report.title,
            "report_type": report.report_type.value,
            "provenance": report.provenance,
            "parameters": dict(sorted(report.parameters.items())),
            "statistics": report.statistics,
            "narrative": report.narrative,
            "sections": report.sections,
            "wafer_map": report.wafer_map,
            "generated_at": report.generated_at.isoformat(),
        }
        return template.render(**context)

    def _html_to_pdf(self, html: str) -> bytes:
        try:
            from weasyprint import HTML  # noqa: PLC0415 — optional native dependency
        except OSError as exc:
            raise ReportRenderError(
                "WeasyPrint system libraries are unavailable; render HTML instead",
                reason=str(exc),
            ) from exc
        except ImportError as exc:
            raise ReportRenderError(
                "WeasyPrint is not installed",
                reason=str(exc),
            ) from exc
        try:
            return cast("bytes", HTML(string=html, encoding="utf-8").write_pdf())
        except Exception as exc:
            raise ReportRenderError(
                "PDF rendering failed",
                reason=str(exc),
            ) from exc
