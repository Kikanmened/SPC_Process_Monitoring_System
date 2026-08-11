"""Archive job: export audit records to durable retention (FR-AU05)."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

from spc_platform.application.context import ApplicationServices
from spc_platform.scheduler.types import JobName, JobResult


def run(
    services: ApplicationServices,
    *,
    log_root: Path,
    data_root: Path,
    state: dict[str, Any],
) -> JobResult:
    """Copy the audit JSONL to a dated archive; identical on re-run for same content."""
    _ = state
    source = log_root / "audit" / "events.jsonl"
    day = services.clock.now().date().isoformat()
    destination = data_root / "archive" / "audit" / f"events-{day}.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_file():
        content = source.read_bytes()
        destination.write_bytes(content)
    else:
        content = b""
        if not destination.is_file():
            destination.write_bytes(content)
        else:
            content = destination.read_bytes()
    # Ensure second run does not append — overwrite with the same bytes.
    if source.is_file():
        shutil.copyfile(source, destination)
        content = destination.read_bytes()
    fingerprint = hashlib.sha256(content).hexdigest()
    return JobResult(
        job_name=JobName.ARCHIVE,
        succeeded=True,
        fingerprint=fingerprint,
        detail={"path": str(destination), "bytes": len(content)},
    )
