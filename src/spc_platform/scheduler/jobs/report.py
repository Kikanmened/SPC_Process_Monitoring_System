"""Daily report job: regenerate SPC summary when series data exists."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path
from typing import Any

from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.report_renderer import RenderTarget
from spc_platform.application.use_cases.generate_report import (
    GenerateReportRequest,
    generate_report,
)
from spc_platform.common.errors import InsufficientDataError, NoActiveBaselineError
from spc_platform.domain.enums import ReportType
from spc_platform.domain.ids import ActorId, ParameterId, ProductId
from spc_platform.scheduler.types import JobName, JobResult

_SCHEDULER_ACTOR = ActorId("scheduler.report")


def run(
    services: ApplicationServices,
    *,
    state: dict[str, Any],
    data_root: Path,
) -> JobResult:
    """Write an HTML SPC summary under ``data_root/reports`` when possible."""
    _ = state
    now = services.clock.now()
    window_start = now - timedelta(days=30)
    output_dir = data_root / "reports" / "scheduled"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "spc_summary.html"
    try:
        artefact = generate_report(
            services,
            actor=_SCHEDULER_ACTOR,
            request=GenerateReportRequest(
                report_type=ReportType.SPC_SUMMARY,
                parameter_id=ParameterId("OXIDE_THK"),
                product_id=ProductId("DEV-A"),
                window_start=window_start,
                window_end=now,
                target=RenderTarget.HTML,
            ),
        )
        output_path.write_bytes(artefact.content)
        fingerprint = hashlib.sha256(artefact.content).hexdigest()
        bytes_written = len(artefact.content)
    except (InsufficientDataError, NoActiveBaselineError):
        fingerprint = hashlib.sha256(b"report-skipped").hexdigest()
        bytes_written = 0
    return JobResult(
        job_name=JobName.DAILY_REPORT,
        succeeded=True,
        fingerprint=fingerprint,
        detail={"bytes": bytes_written, "path": str(output_path)},
    )
