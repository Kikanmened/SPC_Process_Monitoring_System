"""Quarantine a rejected batch with its validation report (NFR-R04)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from spc_platform.common.errors import PipelinePublishError

_BATCH_NAME = "rejected_batch.parquet"
_REPORT_NAME = "validation_report.json"


@dataclass(frozen=True, slots=True)
class QuarantineArtefact:
    """Where a rejected batch and its report were written."""

    directory: Path
    batch_path: Path
    report_path: Path


def quarantine_batch(
    frame: pd.DataFrame,
    *,
    quarantine_root: Path,
    run_id: str,
    report: dict[str, object],
) -> QuarantineArtefact:
    """Write the rejected batch and report under ``quarantine_root / run_id``.

    The interim and processed zones are not touched. A failure here raises —
    losing the evidence of a bad batch is worse than the original defect.
    """
    directory = quarantine_root / run_id
    try:
        directory.mkdir(parents=True, exist_ok=False)
        batch_path = directory / _BATCH_NAME
        report_path = directory / _REPORT_NAME
        frame.to_parquet(batch_path, index=False)
        report_path.write_text(
            json.dumps(report, indent=2, default=str, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        raise PipelinePublishError(
            "failed to write quarantine artefact",
            directory=str(directory),
            reason=str(exc),
        ) from exc
    return QuarantineArtefact(
        directory=directory,
        batch_path=batch_path,
        report_path=report_path,
    )
