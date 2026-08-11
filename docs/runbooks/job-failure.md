# Runbook — scheduled job failure

## When

`/metrics` shows a failed job counter, scheduler logs an exception, or a
platform alert for “any scheduled job failed” fires (DEPLOYMENT_PLAN.md §8).

## Steps

1. Identify the job from the scheduler log (`job`, `error`, `fingerprint` fields).
2. Re-run once without the loop:

   ```bash
   uv run python scripts/ops/run_jobs.py <job-name>
   ```

3. If it succeeds, prove idempotency:

   ```bash
   uv run python scripts/ops/run_jobs.py <job-name> --twice
   ```

4. If it fails again, classify:
   - **Data** — quarantine under `data/archive/quarantine`; fix source schema
   - **Config** — effective config revision in the error context
   - **Storage** — disk, permissions, `SPC_DATA_ROOT` / `SPC_BACKUP_ROOT`
   - **Code** — open an incident; do not silence the failure

## Special case — audit export / archive

Treat as **critical**. A gap in the audit trail cannot be reconstructed.
Document the window, export what remains, and escalate (DEPLOYMENT_PLAN.md §8).

## Verify

Job fingerprints match on a double run; open violations and reports are
unchanged unless new raw data arrived.
