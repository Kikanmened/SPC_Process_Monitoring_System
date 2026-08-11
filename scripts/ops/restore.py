#!/usr/bin/env python3
"""Restore from a backup archive — destructive; requires --confirm."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from spc_platform.infrastructure.runtime_paths import resolve_runtime_paths
from spc_platform.scheduler.jobs.backup import restore_backup


def main(argv: list[str] | None = None) -> int:
    """CLI entry for a restore drill."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path, help="Path to backup-YYYY-MM-DD.tar")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required acknowledgement that restore overwrites processed/ops/audit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the target paths without restoring",
    )
    args = parser.parse_args(argv)
    paths = resolve_runtime_paths()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "archive": str(args.archive),
                    "data_root": str(paths.data_root),
                    "log_root": str(paths.log_root),
                },
                sort_keys=True,
            )
        )
        return 0
    if not args.confirm:
        print("refusing to restore without --confirm", file=sys.stderr)
        return 2
    outcome = restore_backup(
        args.archive,
        data_root=paths.data_root,
        log_root=paths.log_root,
    )
    print(json.dumps(outcome, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
