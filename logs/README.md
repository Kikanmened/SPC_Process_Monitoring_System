# `logs/` — Runtime and Audit Output

## Why this folder exists

Two different obligations happen to both be called "logging", and this folder
keeps them apart because conflating them is a compliance failure waiting to
happen.

**Operational logs** exist to help an engineer debug. They are verbose,
noisy, rotated aggressively, and nobody minds if last Tuesday's DEBUG output
is gone.

**Audit records** exist to prove what the system did and who told it to. Who
changed a control limit and when. Who acknowledged an out-of-control event and
what disposition they recorded. Which data revision produced the number in a
released capability report. These are evidence. They are append-only, retained
per policy, and their deletion is a finding in an IATF 16949 audit.

Same mechanism, entirely different requirements — hence separate sinks,
separate retention, and separate directories.

## Layout

```
logs/
├── app/         Application runtime logs.
├── pipeline/    Per-run ingestion and transformation logs.
├── dashboard/   UI-layer logs, including query performance.
├── audit/       Append-only record of consequential actions.
└── archive/     Rotated logs pending export to the retention store.
```

### `pipeline/`
One log per run, carrying the run identifier, input revision, row counts in
and out, validation failures, and timing. When a chart looks wrong, the first
question is "what did the pipeline do to this data?" and this is where that is
answered without re-running anything.

### `audit/`
Append-only. Records the events that change system behaviour or record a human
decision: control limit changes with their approver, baseline recalculations,
alarm acknowledgements and dispositions, configuration changes, report
generation, and access to confidential data. Never edited, never truncated in
place, exported to durable storage by a job in `scripts/ops/`.

## Conventions

- **Structured JSON to files**, human-readable to the console. A log an
  engineer can read but a machine cannot parse does not scale past one server;
  the reverse does not survive a 03:00 incident.
- Every entry carries a correlation identifier so a request can be traced
  across pipeline, application, and API.
- **No confidential process data or credentials in logs.** Log the parameter
  identifier, not the measured value, unless the value is the point of the
  record. Redaction happens at the logging boundary, not by convention.
- Local files are development convenience only. In a real deployment these
  streams go to a central platform; the directory layout is preserved so the
  mental model does not change between local and production.
- Nothing in this folder is committed.
