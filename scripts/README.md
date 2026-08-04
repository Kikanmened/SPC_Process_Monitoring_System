# `scripts/` — Automation and Operational Entry Points

## Why this folder exists

Every repeated action becomes a script. Not because typing is slow, but
because an undocumented sequence of manual steps is knowledge that lives in
one person's head and disappears when they are on shift elsewhere. A script is
executable documentation: it can be read, reviewed, versioned, and run by
someone who was not there when it was written — including the AI agent, which
should invoke a known-good script rather than reconstruct a command sequence
from inference.

Scripts are **thin**. They parse arguments, call into `spc_platform`, and
report results. A script that grows real logic is a use case that has escaped
into the wrong folder, and it will be untested there.

## Layout

```
scripts/
├── data/         Ingestion, validation, migration, zone promotion.
├── simulation/   Synthetic fab data generation with injected faults.
├── dev/          Environment setup, formatting, local checks.
├── ops/          Scheduled jobs, backfills, baseline recalculation.
├── quality/      Lint, type, security, and documentation gates.
└── ci/           Entry points invoked by GitHub Actions.
```

### `simulation/`
Load-bearing for this project, not a convenience. It generates physically
plausible wafer fab measurement data: baseline process variation with
realistic tool-to-tool and chamber-to-chamber offsets, within-wafer radial
signatures, and deliberately injected faults with known ground truth —
gradual drift, a step shift after maintenance, a cyclic pattern, a variance
increase from a degrading component.

Two things depend on it. The platform becomes demonstrable without any
confidential fab data, and the detection engine becomes *scorable*: because
the injected fault is known, sensitivity and false-alarm rate can be measured
rather than eyeballed.

### `ops/`
The jobs that keep a live deployment healthy: scheduled ingestion, baseline
recalculation after a qualified process change, archival, and alert digest
generation. Each is idempotent — a job that corrupts state when run twice will
eventually be run twice.

### `ci/`
`gate.sh` is the single definition of every quality gate. `make check`,
the pre-commit hooks, and the jobs in `.github/workflows/` all call it by gate
name and hold no copy of a command themselves — so a green local run and a
green pipeline cannot come to mean different things, and switching CI provider
is a configuration change rather than a rewrite.

Alongside it: `check_docs_links.py` (internal links and anchors),
`check_coverage.py` (non-regression in `domain/` and `analytics/`),
`check_commit_message.py` (Conventional Commits), and `gitleaks.sh`, which
fetches and checksum-verifies the pinned secret scanner.

### `quality/`
Standalone quality analyses that are *not* gates — one-off audits and reports
run deliberately rather than on every commit. The gates themselves live in
`ci/` precisely because they are shared by three callers.

## Conventions

- Python for anything non-trivial; shell only for genuine shell work.
- Every script supports `--help` and states what it will do.
- Destructive operations require an explicit confirmation flag and support
  `--dry-run`.
- Idempotent by default.
- Exit codes are meaningful: zero means success, and nothing else does.
- Logs go to stdout in a readable form and to `logs/` in structured form.
