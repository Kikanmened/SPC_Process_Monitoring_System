"""Ingest job: process new raw files; skip already-seen content hashes."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.measurement_source import BatchRequest
from spc_platform.config import load_settings
from spc_platform.config.profiles import Profile
from spc_platform.infrastructure.readers.file_source import (
    FileMeasurementSource,
    load_raw_frame,
)
from spc_platform.pipelines.paths import PipelinePaths
from spc_platform.pipelines.run import PipelineDependencies, run_pipeline
from spc_platform.scheduler.types import JobName, JobResult


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def run(
    services: ApplicationServices,
    *,
    data_root: Path,
    state: dict[str, Any],
) -> JobResult:
    """Ingest every new CSV/Parquet under ``data_root/raw`` (not ``raw/accepted``)."""
    raw_root = data_root / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    prior = state.get("ingest", {})
    prior_detail = prior.get("detail", {}) if isinstance(prior, dict) else {}
    seen: set[str] = set(prior_detail.get("seen_hashes", []))
    newly_ingested = 0

    candidates = sorted(
        [path for path in [*raw_root.glob("*.csv"), *raw_root.glob("*.parquet")] if path.is_file()],
        key=lambda path: path.name,
    )
    if not candidates:
        fingerprint = hashlib.sha256(b"ingest-empty").hexdigest()
        return JobResult(
            job_name=JobName.INGEST,
            succeeded=True,
            fingerprint=fingerprint,
            detail={"newly_ingested": 0, "seen_hashes": sorted(seen)},
        )

    settings = load_settings(Profile.LOCAL)
    for source_path in candidates:
        content_hash = _file_hash(source_path)
        if content_hash in seen:
            continue
        source = FileMeasurementSource(identity=str(source_path.resolve()))
        destination = data_root / "raw" / "accepted" / source_path.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor = source.materialise(
            BatchRequest(path=source_path),
            destination,
        )
        frame = load_raw_frame(Path(descriptor.location))
        run_pipeline(
            frame,
            source_identity=descriptor.identity,
            dependencies=PipelineDependencies(
                clock=services.clock,
                registry=settings.unit_registry(),
                paths=PipelinePaths(
                    quarantine_root=data_root / "archive" / "quarantine",
                    interim_directory=data_root / "interim",
                    processed_directory=data_root / "processed",
                ),
                repository=None,
            ),
        )
        seen.add(content_hash)
        newly_ingested += 1

    fingerprint = hashlib.sha256("|".join(sorted(seen)).encode("utf-8")).hexdigest()
    return JobResult(
        job_name=JobName.INGEST,
        succeeded=True,
        fingerprint=fingerprint,
        detail={
            "newly_ingested": newly_ingested,
            "seen_hashes": sorted(seen),
            "candidate_count": len(candidates),
        },
    )
