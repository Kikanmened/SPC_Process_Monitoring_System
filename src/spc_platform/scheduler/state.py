"""Persistent job-state fingerprints for idempotency checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_job_state(path: Path) -> dict[str, Any]:
    """Load JSON job state, or empty mapping when absent."""
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = "job state must be a JSON object"
        raise TypeError(msg)
    return payload


def save_job_state(path: Path, state: dict[str, Any]) -> None:
    """Write job state atomically via a temp file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(state, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
