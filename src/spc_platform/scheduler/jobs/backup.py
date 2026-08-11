"""Backup job: snapshot data + audit into a restorable archive (NFR-R03)."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
from pathlib import Path
from typing import Any

from spc_platform.application.context import ApplicationServices
from spc_platform.scheduler.types import JobName, JobResult


def _reset_tarinfo(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo:
    """Strip host metadata so re-runs produce comparable archives."""
    tarinfo.mtime = 0
    tarinfo.uid = 0
    tarinfo.gid = 0
    tarinfo.uname = ""
    tarinfo.gname = ""
    return tarinfo


def _add_tree(archive: tarfile.TarFile, root: Path, arcname: str) -> None:
    if not root.exists():
        return
    archive.add(root, arcname=arcname, recursive=True, filter=_reset_tarinfo)


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree_entries(root: Path, prefix: str) -> list[tuple[str, str]]:
    if not root.exists():
        return []
    entries: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = f"{prefix}/{path.relative_to(root).as_posix()}"
            entries.append((rel, _file_digest(path)))
    return entries


def run(
    services: ApplicationServices,
    *,
    data_root: Path,
    log_root: Path,
    backup_root: Path,
    state: dict[str, Any],
) -> JobResult:
    """Create ``backup-<date>.tar``; fingerprint is content-based (NFR-R01)."""
    _ = state
    day = services.clock.now().date().isoformat()
    backup_root.mkdir(parents=True, exist_ok=True)
    archive_path = backup_root / f"backup-{day}.tar"
    manifest = {
        "created_at": services.clock.now().isoformat(),
        "data_root": str(data_root),
        "log_root": str(log_root),
    }
    manifest_path = backup_root / f"backup-{day}.manifest.json"
    manifest_text = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8")

    # Fingerprint logical payload, not tar packaging bytes (mtimes vary).
    # Omit ops/job_state — rewritten after every job.
    payload = {
        "manifest": manifest,
        "files": [
            *_tree_entries(data_root / "processed", "processed"),
            *_tree_entries(data_root / "interim", "interim"),
            *_tree_entries(log_root / "audit", "audit"),
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

    with tarfile.open(archive_path, mode="w") as archive:
        _add_tree(archive, data_root / "processed", "processed")
        _add_tree(archive, data_root / "interim", "interim")
        _add_tree(archive, log_root / "audit", "audit")
        archive.add(manifest_path, arcname="manifest.json", filter=_reset_tarinfo)

    archive_digest = _file_digest(archive_path)
    (backup_root / f"backup-{day}.sha256").write_text(archive_digest + "\n", encoding="utf-8")
    return JobResult(
        job_name=JobName.BACKUP,
        succeeded=True,
        fingerprint=fingerprint,
        detail={
            "archive": str(archive_path),
            "sha256": archive_digest,
            "content_fingerprint": fingerprint,
            "bytes": archive_path.stat().st_size,
        },
    )


def restore_backup(archive_path: Path, *, data_root: Path, log_root: Path) -> dict[str, Any]:
    """Restore processed/ops/audit trees from a backup tar (tested drill)."""
    if not archive_path.is_file():
        msg = f"backup archive not found: {archive_path}"
        raise FileNotFoundError(msg)
    staging = data_root / "_restore_tmp"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive_path, mode="r") as archive:
            archive.extractall(path=staging, filter="data")
        for name, target in (
            ("processed", data_root / "processed"),
            ("interim", data_root / "interim"),
            ("audit", log_root / "audit"),
        ):
            source = staging / name
            if not source.exists():
                continue
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
        return {
            "archive": str(archive_path),
            "restored_data_root": str(data_root),
            "restored_log_root": str(log_root),
        }
    finally:
        if staging.exists():
            shutil.rmtree(staging)
