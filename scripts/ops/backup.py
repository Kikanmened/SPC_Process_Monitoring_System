#!/usr/bin/env python3
"""Create a restorable backup archive (DEPLOYMENT_PLAN.md §6)."""

from __future__ import annotations

import argparse
import json
import sys

from spc_platform.infrastructure.composition import build_local_bundle
from spc_platform.infrastructure.runtime_paths import resolve_runtime_paths
from spc_platform.scheduler.jobs.backup import run as run_backup
from spc_platform.scheduler.state import load_job_state, save_job_state


def main(argv: list[str] | None = None) -> int:
    """CLI entry for a one-shot backup."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    paths = resolve_runtime_paths()
    bundle = build_local_bundle()
    state = load_job_state(paths.job_state)
    result = run_backup(
        bundle.services,
        data_root=paths.data_root,
        log_root=paths.log_root,
        backup_root=paths.backup_root,
        state=state,
    )
    state["backup"] = {
        "fingerprint": result.fingerprint,
        "detail": result.detail,
        "succeeded": result.succeeded,
    }
    save_job_state(paths.job_state, state)
    print(json.dumps(result.detail, sort_keys=True))
    return 0 if result.succeeded else 1


if __name__ == "__main__":
    sys.exit(main())
