# Module 1 — Data Ingestion

**Owning layers:** `pipelines/ingest/`, `infrastructure/readers/`
**Depends on:** Module 10
**Depended on by:** Module 2
**Requirement coverage:** FR-D01 – FR-D04, FR-D09 – FR-D11; NFR-P06, NFR-R01, NFR-R04
**Delivered in:** Phase 10 · **Status:** Design — not implemented

---

## Purpose

The boundary at which untrusted data becomes trusted data. Every module
downstream computes as though its input is intact, correctly typed, and
attributable to a source — this is the module that makes that assumption safe.

Its bias is deliberate and one-directional: rejecting a good batch costs a rerun,
while accepting a bad one produces a confident wrong chart that nobody
questions. Repair is never attempted here. A malformed record is a quarantined
batch and a failed run, not a coerced float (R-06).

## Responsibilities

- Read raw exports through a source adapter, treating `data/raw/` as immutable.
- Validate every record against the declared raw-zone schema, as a hard stop
  (FR-D02, FR-D03).
- Reject timezone-naive timestamps outright (FR-D04). Clock skew between process
  and metrology tools produces misordered series that present as statistical
  defects and are data integrity defects (SEMI E148,
  [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) §9).
- Fail the run on duplicate measurement keys rather than dropping or
  de-duplicating rows (FR-D10).
- Carry the full measurement context through unchanged, including `chamber_id`
  and `metrology_tool_id` (FR-D01, [DATASET_GUIDE.md](../DATASET_GUIDE.md) §3.1).
- Quarantine the failing batch with its validation report, leaving no partial
  state in any downstream zone (NFR-R04).
- Assign a `data_revision` to every accepted row and emit one run record with
  counts in and out (FR-D09).
- Remain idempotent: re-ingesting the same batch produces identical state, not a
  duplicate (NFR-R01).
- Define the source port so a future MES/YMS adapter changes nothing downstream
  (FR-D11).

**Not this module's work:** unit conversion, re-measurement resolution, outlier
flagging, and subgrouping all belong to Module 2. Ingestion changes no value.

## Public interfaces

```python
class MeasurementSource(Protocol):
    """Port for anything that can supply raw measurement records."""

    def describe(self) -> SourceDescriptor: ...
    def read_batch(self, request: BatchRequest) -> RawBatch: ...


def ingest_batch(
    batch: RawBatch,
    schema: RawZoneSchema,
    keys: MeasurementKeyDefinition,
    clock: Clock,
) -> IngestionResult:
    """Validate and admit one batch, or raise without side effects."""
```

`IngestionResult` carries the admitted dataset reference, the assigned
`data_revision`, and the `IngestionRunRecord`. Failure is signalled by a typed
exception, never by a partially populated result:

| Exception | Raised when |
|---|---|
| `SchemaValidationError` | Any record fails the raw-zone schema; carries the failure cases |
| `NaiveTimestampError` | A timestamp lacks timezone information; carries column and row count |
| `DuplicateMeasurementKeyError` | The declared key is not unique; carries the colliding keys |
| `SourceUnavailableError` | The adapter cannot reach its source; never a silent empty batch |

## Dependencies

| Depends on | For |
|---|---|
| Module 10 | Typed ingestion configuration, injected `Clock`, error taxonomy, provenance capture, audit sink |
| `domain/` | `Measurement` field vocabulary, identifier `NewType`s, `DataRevision` |
| pandas, PyArrow, Pandera | Confined to `infrastructure/readers/` and the validation stage |

No dependency on any analytics code. Ingestion never computes a statistic.

## Expected inputs

| Input | Source | Notes |
|---|---|---|
| Raw export files | `data/raw/`, or a source adapter | CSV at the raw boundary, Parquet thereafter |
| Batch manifest | Alongside the export | Source identity, expected row count, export timestamp |
| Raw-zone schema | `data/schemas/` | Pandera declaration ([DATASET_GUIDE.md](../DATASET_GUIDE.md) §3.3) |
| Ingestion configuration | `configs/base/` | Source registry, key definition, quarantine location |
| Clock | Injected | No module reads the wall clock directly |

## Expected outputs

| Output | Destination | Contents |
|---|---|---|
| Admitted dataset | `data/interim/` | Every input field, unmodified, plus `data_revision` |
| `IngestionRunRecord` | Lineage store, `logs/pipeline/` | Run ID, source, counts in and out, validation summary, revisions |
| Quarantine artefact | `data/archive/quarantine/` | The rejected batch and its full validation report |
| Audit event | `logs/audit/` | Pipeline run with inputs, outputs, and validation result (QA plan §2.2) |

## Files to create

```
src/spc_platform/pipelines/ingest/__init__.py
src/spc_platform/pipelines/ingest/stage.py          ingest_batch orchestration
src/spc_platform/pipelines/ingest/validation.py     schema application, hard stop
src/spc_platform/pipelines/ingest/keys.py           key definition and duplicate detection
src/spc_platform/pipelines/ingest/quarantine.py     rejected batch handling
src/spc_platform/pipelines/lineage.py               data_revision assignment, run records
src/spc_platform/application/ports/measurement_source.py
src/spc_platform/infrastructure/readers/__init__.py
src/spc_platform/infrastructure/readers/csv_export.py
src/spc_platform/infrastructure/readers/parquet_export.py
src/spc_platform/domain/lineage.py                  DataRevision, IngestionRunRecord
data/schemas/raw_measurement.py                     Pandera schema, raw zone
configs/base/ingestion.yaml                         source registry and key definition
```

## Testing requirements

| Tier | What it must establish |
|---|---|
| `unit/` | Each failure mode raises its specific exception with context, and writes nothing downstream. A valid batch passes every field through byte-identically. |
| `contract/` | One port suite that the CSV reader, the Parquet reader, and the in-memory fake all pass, so unit tests using the fake prove something about the real adapters. |
| `integration/` | Real CSV and Parquet round-trips, including timezone handling on the wire and dtype coercion behaviour that mocks conceal. |
| `e2e/` | A generated batch with a deliberately embedded defect fails the run, quarantines, and leaves `data/interim/` untouched. |
| `performance/` | Sustained ingestion at 10⁶ records/day (NFR-P06). |

Property-based obligation: ingesting the same batch twice yields identical state
and one additional run record, not duplicated rows.

## Documentation required

- `docs/api/ingestion.md` — the source port contract: types, units,
  preconditions, exceptions, and the guarantee that no value is altered.
- `docs/runbooks/ingestion-failure.md` — what a quarantined batch looks like,
  how to read the validation report, and how to re-run after correction.
- Update `data/raw/README.md` and `data/interim/README.md` with the zone
  contract this module enforces.
- Update [DATASET_GUIDE.md](../DATASET_GUIDE.md) §3.3 if a schema field changes.

## Future extension points

- **MES/YMS adapter** — implement `MeasurementSource` in `infrastructure/`;
  nothing downstream changes (FR-D11, the reason the port exists from day one).
- **Equipment communication** — a SECS/GEM or EDA-speaking adapter sits at the
  same seam ([domain/SEMI_STANDARDS_ALIGNMENT.md](../domain/SEMI_STANDARDS_ALIGNMENT.md)).
- **Additional export formats** — a new reader, an unchanged stage.
- **Incremental and backfill ingestion** — the run record already carries the
  window; a watermark strategy is additive.
- **Streaming** — deliberately excluded from the base design; the port shape does
  not prevent it if a use case ever requires sub-minute latency.

---

**Related:** [MODULE_DESIGN.md](../MODULE_DESIGN.md) ·
[02-data-preprocessing.md](02-data-preprocessing.md) ·
[DATASET_GUIDE.md](../DATASET_GUIDE.md)
