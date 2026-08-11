"""NFR-R01: every scheduled job leaves identical fingerprints on a second run."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.factories.application import seeded_bundle

from spc_platform.infrastructure.runtime_paths import RuntimePaths
from spc_platform.scheduler.runner import run_job_twice
from spc_platform.scheduler.types import JobName


@pytest.mark.unit
@pytest.mark.parametrize(
    "job_name",
    [
        JobName.EVALUATE,
        JobName.NOTIFY,
        JobName.DAILY_REPORT,
        JobName.ARCHIVE,
        JobName.BACKUP,
        JobName.INGEST,
    ],
)
def test_job_is_idempotent(job_name: JobName, tmp_path: Path) -> None:
    bundle = seeded_bundle(outlier=11.5)
    paths = RuntimePaths(
        data_root=tmp_path / "data",
        log_root=tmp_path / "logs",
        backup_root=tmp_path / "backups",
    )
    paths.ensure()
    (paths.log_root / "audit" / "events.jsonl").write_text(
        '{"record_id":"aud-1","event_type":"pipeline_run",'
        '"actor":"scheduler","timestamp":"2025-07-15T12:00:00+00:00",'
        '"reason":"","before":{},"after":{},"provenance":null,"succeeded":true}\n',
        encoding="utf-8",
    )
    first, second = run_job_twice(bundle.services, job_name, paths)
    assert first.fingerprint == second.fingerprint
    assert first.succeeded is True
