"""FR-RP03: identical regeneration from the same revisions; provenance header."""

from __future__ import annotations

import re

import pytest
from tests.factories.application import ACTOR, WINDOW_END, WINDOW_START, seeded_bundle

from spc_platform.application.ports.report_renderer import RenderTarget
from spc_platform.application.use_cases import GenerateReportRequest, generate_report
from spc_platform.domain.enums import ReportType
from spc_platform.domain.ids import ParameterId, ProductId

_PROVENANCE_MARKERS = (
    "data_revision",
    "code_revision",
    "config_revision",
    "generated_at",
    'data-provenance="required"',
)


@pytest.mark.contract
@pytest.mark.parametrize(
    "report_type",
    [
        ReportType.SPC_SUMMARY,
        ReportType.CAPABILITY_STUDY,
    ],
)
def test_report_regenerates_identically(report_type: ReportType) -> None:
    bundle = seeded_bundle()
    request = GenerateReportRequest(
        report_type=report_type,
        parameter_id=ParameterId("OXIDE_THK"),
        product_id=ProductId("DEV-A"),
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        target=RenderTarget.HTML,
    )
    first = generate_report(bundle.services, actor=ACTOR, request=request)
    second = generate_report(bundle.services, actor=ACTOR, request=request)
    assert first.content == second.content
    assert first.provenance.data_revision == second.provenance.data_revision
    assert first.provenance.code_revision == second.provenance.code_revision
    assert first.provenance.config_revision == second.provenance.config_revision


@pytest.mark.contract
def test_provenance_header_on_every_artefact_type() -> None:
    bundle = seeded_bundle()
    for report_type in (ReportType.SPC_SUMMARY, ReportType.CAPABILITY_STUDY):
        artefact = generate_report(
            bundle.services,
            actor=ACTOR,
            request=GenerateReportRequest(
                report_type=report_type,
                parameter_id=ParameterId("OXIDE_THK"),
                product_id=ProductId("DEV-A"),
                window_start=WINDOW_START,
                window_end=WINDOW_END,
                target=RenderTarget.HTML,
            ),
        )
        html = artefact.content.decode("utf-8")
        for marker in _PROVENANCE_MARKERS:
            assert marker in html
        assert re.search(r"<dd>rev-app-1</dd>", html)
        assert "n" in html.lower()
