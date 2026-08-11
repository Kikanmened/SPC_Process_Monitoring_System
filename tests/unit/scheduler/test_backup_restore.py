"""NFR-R03: restore from backup is tested, not assumed."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.factories.application import seeded_bundle

from spc_platform.infrastructure.runtime_paths import RuntimePaths
from spc_platform.scheduler.jobs.backup import restore_backup
from spc_platform.scheduler.jobs.backup import run as run_backup
from spc_platform.scheduler.runner import run_job
from spc_platform.scheduler.types import JobName


@pytest.mark.unit
def test_backup_restore_roundtrip(tmp_path: Path) -> None:
    bundle = seeded_bundle()
    data_root = tmp_path / "data"
    log_root = tmp_path / "logs"
    backup_root = tmp_path / "backups"
    processed = data_root / "processed"
    processed.mkdir(parents=True)
    marker = processed / "marker.txt"
    marker.write_text("keep-me\n", encoding="utf-8")
    (log_root / "audit").mkdir(parents=True)
    (log_root / "audit" / "events.jsonl").write_text("audit-line\n", encoding="utf-8")

    result = run_backup(
        bundle.services,
        data_root=data_root,
        log_root=log_root,
        backup_root=backup_root,
        state={},
    )
    archive = Path(str(result.detail["archive"]))
    assert archive.is_file()
    assert (
        backup_root / f"backup-{bundle.services.clock.now().date().isoformat()}.sha256"
    ).is_file()

    marker.write_text("corrupted\n", encoding="utf-8")
    (log_root / "audit" / "events.jsonl").write_text("lost\n", encoding="utf-8")

    restore_backup(archive, data_root=data_root, log_root=log_root)
    assert marker.read_text(encoding="utf-8") == "keep-me\n"
    assert (log_root / "audit" / "events.jsonl").read_text(encoding="utf-8") == "audit-line\n"


@pytest.mark.unit
def test_backup_job_via_runner(tmp_path: Path) -> None:
    bundle = seeded_bundle()
    paths = RuntimePaths(
        data_root=tmp_path / "data",
        log_root=tmp_path / "logs",
        backup_root=tmp_path / "backups",
    )
    paths.ensure()
    outcome = run_job(bundle.services, JobName.BACKUP, paths)
    assert outcome.succeeded
    assert Path(str(outcome.detail["archive"])).is_file()
