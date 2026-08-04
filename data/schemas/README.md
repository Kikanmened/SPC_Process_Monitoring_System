# `data/schemas/` — Data-zone contracts

Authoritative Pandera schemas live in
`src/spc_platform/pipelines/schemas/`, beside the pipeline stages that enforce
them. This directory holds documentation and any non-code contract artefacts.

| Zone | Schema | Enforced at |
|---|---|---|
| `raw/` | `RawMeasurementSchema` | Ingest (Module 1) |
| `interim/` | `InterimMeasurementSchema` | Preprocessing entry |
| `processed/` | `ProcessedMeasurementSchema` | Publish (Module 2) |

Validation is a **hard stop**. A schema violation quarantines the batch and
fails the run — never coerces a malformed value into a plausible float
(DATASET_GUIDE.md §3.3, FR-D03).
