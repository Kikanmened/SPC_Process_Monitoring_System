# `data/` — Data Zones

## Why this folder exists

Manufacturing data arrives dirty, in inconsistent units, with re-measurements,
aborted lots, and equipment downtime baked in. Treating "the data" as a single
undifferentiated pile is how analyses become unreproducible and how a cleaning
decision made months ago silently invalidates a capability study.

This folder implements an **immutable-zone architecture**. Data flows in one
direction only, each zone has a defined contract, and no stage ever writes
back into the zone it read from. The transformation between zones is code in
`src/spc_platform/pipelines/`, so the state of any zone can be reconstructed
from an earlier zone plus a git revision.

## Zones

```
data/
├── raw/         Untouched source exports. Write-once, read-only, forever.
├── external/    Third-party reference data not produced by our fab.
├── interim/     Intermediate output of partially applied pipeline stages.
├── processed/   Analysis-ready, schema-validated, canonical units.
├── synthetic/   Generated fab data for development and demonstration.
├── reference/   Small master data: spec limits, tool registry, control plans.
├── schemas/     The contracts every zone is validated against.
└── archive/     Retired snapshots retained for traceability.
```

### `raw/`
Byte-for-byte as received from the MES, YMS, metrology tool, or equipment log.
Never edited, never overwritten, never "quickly fixed" — a correction applied
in `raw/` is a correction that no one can audit later. If the source is wrong,
the fix belongs in a pipeline stage where it is versioned, tested, and
explained.

### `external/`
Data we did not produce: supplier certificates, material lot data, reference
distributions, calendar and shift schedules. Kept separate from `raw/` because
its provenance, refresh cadence, and trust level are different.

### `interim/`
Pipeline scratch space. Safe to delete at any time; the pipeline rebuilds it.
Nothing may read from `interim/` except the next pipeline stage — in
particular, no notebook, dashboard, or report may source data from here.

### `processed/`
The single source of truth for analysis. Schema-validated, canonical units
(nm, °C, sccm, Ω·cm — stated explicitly, never inferred), with lineage
metadata attached. The dashboard, notebooks, and reports read from here and
only from here.

### `synthetic/`
Physically plausible generated fab data: normal process variation with
realistic tool-to-tool and chamber-to-chamber offsets, and deliberately
injected signatures — gradual drift, a step shift after a maintenance event,
a cyclic pattern tracking chamber temperature, increased variance from a
degrading component.

This zone is what makes the project demonstrable and testable without
confidential data. It also serves a second purpose: because the injected
faults have known ground truth, the detection engine can be scored on
sensitivity and false-alarm rate rather than merely inspected by eye.
Generators live in `scripts/simulation/`.

### `reference/`
Small, human-reviewable master data that changes rarely and matters
enormously: specification limits per device and layer, the process step and
tool registry, control plan definitions, parameter-to-chart-type mappings.
This is **versioned in git** because a change to a spec limit is an engineering
decision that requires a reviewable history and an approver.

### `schemas/`
Explicit contracts — column names, dtypes, units, allowed ranges, nullability,
key cardinality. Validation happens at zone boundaries, and a violation stops
the pipeline. Silent coercion of a malformed measurement into a valid-looking
float is the single most dangerous failure mode in this system.

### `archive/`
Frozen snapshots that back a released report or a closed quality
investigation. Retained for traceability, never used as a live input.

## Retention and version control

Only `reference/` and `schemas/` are committed. Everything else is ignored by
`data/.gitignore`, because git is not a data lake and wafer-level measurement
data is confidential in a foundry context. Reproducibility comes from
versioned generators and pipelines, not from stored blobs.

## Rules

- Never edit a file in `raw/`. Ever.
- Every file entering `processed/` passes schema validation first.
- Units are declared in the schema, not implied by a column name.
- No credentials, no customer-identifying device names, and no confidential
  process parameters in any committed file.
- If an analysis cannot be reproduced from `raw/` (or `synthetic/`) plus a git
  revision, it is not finished.
