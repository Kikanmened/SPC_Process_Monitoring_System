"""Filesystem roots for local and container deployments."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """Resolved data, log, and backup directories."""

    data_root: Path
    log_root: Path
    backup_root: Path

    @property
    def raw(self) -> Path:
        """Incoming raw exports."""
        return self.data_root / "raw"

    @property
    def interim(self) -> Path:
        """Validated interim zone."""
        return self.data_root / "interim"

    @property
    def processed(self) -> Path:
        """Processed zone (DuckDB / Parquet)."""
        return self.data_root / "processed"

    @property
    def quarantine(self) -> Path:
        """Quarantine for failed ingest."""
        return self.data_root / "archive" / "quarantine"

    @property
    def audit_log(self) -> Path:
        """Append-only audit JSONL."""
        return self.log_root / "audit" / "events.jsonl"

    @property
    def job_state(self) -> Path:
        """Idempotency state for scheduled jobs."""
        return self.data_root / "ops" / "job_state.json"

    def ensure(self) -> None:
        """Create directory skeleton used by jobs and backup."""
        for path in (
            self.raw,
            self.interim,
            self.processed,
            self.quarantine,
            self.audit_log.parent,
            self.backup_root,
            self.job_state.parent,
        ):
            path.mkdir(parents=True, exist_ok=True)


def resolve_runtime_paths() -> RuntimePaths:
    """Read roots from the environment with repository-relative defaults."""
    cwd = Path.cwd()
    paths = RuntimePaths(
        data_root=Path(os.environ.get("SPC_DATA_ROOT", cwd / "data")),
        log_root=Path(os.environ.get("SPC_LOG_ROOT", cwd / "logs")),
        backup_root=Path(os.environ.get("SPC_BACKUP_ROOT", cwd / "data" / "archive" / "backups")),
    )
    paths.ensure()
    return paths
