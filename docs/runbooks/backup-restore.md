# Runbook — backup and restore drill

## When

Nightly backup verification, pre-release restore drill, or recovery after
corruption of `processed/` or audit files.

## Backup

```bash
make backup
# or: uv run python scripts/ops/backup.py
```

Artefacts land under `SPC_BACKUP_ROOT` (default `data/archive/backups/`):

- `backup-YYYY-MM-DD.tar`
- `backup-YYYY-MM-DD.sha256` (archive bytes)
- `backup-YYYY-MM-DD.manifest.json`

Job idempotency fingerprints the logical payload (processed/interim/audit +
manifest), not tar packaging metadata.

## Restore (destructive)

```bash
uv run python scripts/ops/restore.py data/archive/backups/backup-YYYY-MM-DD.tar --dry-run
uv run python scripts/ops/restore.py data/archive/backups/backup-YYYY-MM-DD.tar --confirm
```

Restores `processed/`, `interim/`, and `logs/audit/` from the archive.

## Verify (NFR-R03)

1. Write a known marker file under `data/processed/`.
2. Run backup.
3. Corrupt or delete the marker.
4. Restore with `--confirm`.
5. Confirm the marker content matches the pre-backup value.

Automated coverage: `tests/unit/scheduler/test_backup_restore.py`.

## Failure modes

| Symptom | Action |
|---|---|
| Archive missing | Re-run backup; check `SPC_BACKUP_ROOT` |
| SHA mismatch | Do not restore; investigate write failure |
| Refused without `--confirm` | Intentional safeguard — re-run with the flag |
