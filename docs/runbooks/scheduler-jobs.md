# Runbook — scheduled jobs

## Job set

| Job | Purpose |
|---|---|
| `ingest` | New files under `data/raw/` → processed (skip known hashes) |
| `evaluate` | Lot evaluation once per data revision |
| `notify` | Digested notifications when the open set changes |
| `daily-report` | SPC summary HTML under `data/reports/scheduled/` |
| `archive` | Copy audit JSONL to dated retention path |
| `backup` | Tar snapshot of processed/interim/audit |

## Run once

```bash
uv run python scripts/ops/run_jobs.py ingest evaluate notify archive backup
```

## Prove idempotency (NFR-R01)

```bash
make jobs
# or: uv run python scripts/ops/run_jobs.py … --twice
```

Each job must report identical fingerprints on the second run.

## Loop (container / systemd)

```bash
python -m spc_platform.scheduler --loop --interval 900
```

## Failure modes

| Symptom | Action |
|---|---|
| Ingest quarantine growth | Inspect `data/archive/quarantine`; fix schema |
| Notify skipped forever | Confirm open violations exist; check digest state |
| Job fingerprint drift | Treat as a defect — job is not idempotent |
