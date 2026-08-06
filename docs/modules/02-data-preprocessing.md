# Module 2 — Data Preprocessing

**Owning layers:** `pipelines/transform/`, `domain/`, `infrastructure/repositories/`
**Depends on:** Modules 1, 10
**Depended on by:** Modules 3, 4, 6
**Requirement coverage:** FR-D05 – FR-D08, FR-C04; NFR-R04, NFR-CO02
**Delivered in:** Phase 10 · **Status:** Implemented

---

## Purpose

Turn validated records into an analysis-ready series without quietly changing
what was measured. Every transformation here is explicit, recorded in lineage,
and reversible in the sense that the original row survives.

The module also owns the single most consequential modelling decision in the
platform: **how measurements are grouped into subgroups**. Get it wrong and the
control chart is decorative — sites pooled as a rational subgroup absorb the
systematic within-wafer radial signature into σ̂_within, the limits widen, the
chart never signals, and the team concludes SPC does not work here (R-04).

## Responsibilities

- Convert units explicitly, recording the conversion in lineage; never infer a
  unit from a magnitude (FR-D08).
- Resolve re-measurements by marking the superseded record, never deleting it
  (FR-D05). `measurement_status` moves to `superseded`; the row remains.
- Never impute a missing measurement in the SPC path (FR-D06). A gap is a gap.
- Flag outliers with the rule that flagged them; never remove them
  automatically (FR-D07).
- Attach process context — step, tool, chamber, recipe, product, metrology tool
  — so every measurement is traceable end to end (NFR-CO02).
- Build subgroups according to the strategy declared for the parameter, and
  record that strategy on every subgroup produced (FR-C04).
- Publish to `data/processed/` atomically, so a failed run leaves no partial
  state (NFR-R04).
- Serve the analysis-ready series through the measurement repository port.

**The subgrouping default is deliberate:** sites within a wafer are *not* a
rational subgroup. Wafer-level statistics are charted and the within-wafer
signature is analysed spatially by Module 6. A configuration that groups sites
must state so explicitly and is refused unless the parameter declares it.

## Public interfaces

```python
class PipelineStage(Protocol):
    """One named, independently testable transformation with lineage."""

    name: str

    def apply(self, frame: StageFrame, context: StageContext) -> StageResult: ...


class MeasurementRepository(Protocol):
    """Read port over the processed zone. Implemented for DuckDB, PostgreSQL, and a fake."""

    def series_for(self, query: SeriesQuery) -> MeasurementSeries: ...
    def sites_for(self, query: WaferQuery) -> SiteMeasurements: ...


def build_subgroups(
    series: MeasurementSeries,
    strategy: SubgroupingStrategy,
) -> Sequence[Subgroup]:
    """Group a series for charting, stamping the strategy on every subgroup."""
```

| Exception | Raised when |
|---|---|
| `UnitConversionError` | No declared conversion exists between source and target unit |
| `AmbiguousRemeasurementError` | Two records claim the same key with no resolvable ordering |
| `SubgroupingError` | The declared strategy cannot be applied to the series shape |
| `InsufficientDataError` | A subgroup falls below the configured minimum size |

## Dependencies

| Depends on | For |
|---|---|
| Module 1 | The admitted interim dataset and its `data_revision` |
| Module 10 | Unit registry, injected clock, typed configuration, lineage and audit sinks |
| `domain/` | `Measurement`, `Subgroup`, `SubgroupingStrategy`, identifier types |
| pandas, PyArrow, Pandera | Confined to the pipeline and repository adapters |

Analytics never sees a DataFrame. This module is where tabular data ends and
arrays begin ([TECH_STACK.md](../TECH_STACK.md) §3).

## Expected inputs

| Input | Source | Notes |
|---|---|---|
| Admitted interim dataset | Module 1 | Unmodified values with `data_revision` |
| Parameter registry | `data/reference/parameters.yaml` | Declared unit, metrology method, sampling plan |
| Subgrouping configuration | `configs/spc/` | Per parameter; sites-as-subgroup requires explicit declaration |
| Interim and processed zone schemas | `data/schemas/` | Validated at both boundaries |
| Outlier flagging policy | `configs/spc/` | Rule identity recorded with each flag |

## Expected outputs

| Output | Destination | Contents |
|---|---|---|
| Processed measurement set | `data/processed/` | Normalised units, resolved status, attached context, `data_revision` |
| `Subgroup[]` | In memory, to Module 3 | Statistic inputs plus the strategy that produced them |
| Stage lineage records | `logs/pipeline/` | Per stage: rows in, rows out, transformations applied |
| Flag records | Processed zone | Outlier and suspect flags with the rule that raised them |

Row counts in and out are recorded per stage precisely so that "which stage did
this?" is answerable at 03:00 without re-running anything.

## Files to create

```
src/spc_platform/pipelines/transform/__init__.py
src/spc_platform/pipelines/transform/normalise_units.py
src/spc_platform/pipelines/transform/resolve_remeasurements.py
src/spc_platform/pipelines/transform/attach_context.py
src/spc_platform/pipelines/transform/flag_outliers.py
src/spc_platform/pipelines/transform/subgroup.py
src/spc_platform/pipelines/transform/publish.py            atomic write to processed
src/spc_platform/pipelines/stage.py                        PipelineStage protocol
src/spc_platform/domain/subgrouping.py                     SubgroupingStrategy, Subgroup
src/spc_platform/domain/measurement_series.py
src/spc_platform/application/ports/measurement_repository.py
src/spc_platform/infrastructure/repositories/duckdb_measurements.py
src/spc_platform/infrastructure/repositories/postgres_measurements.py
src/spc_platform/infrastructure/repositories/fake_measurements.py
data/schemas/interim_measurement.py
data/schemas/processed_measurement.py
configs/spc/subgrouping.yaml
```

## Testing requirements

| Tier | What it must establish |
|---|---|
| `unit/` | Every stage in isolation, including each refusal. A superseded record is retained. An imputation attempt is impossible. An outlier is flagged and still present in the output. |
| `contract/` | The repository port suite passes identically against DuckDB, PostgreSQL, and the fake — the guarantee that makes unit-test fakes meaningful. |
| `statistical/` | Subgrouping correctness: σ̂_within computed from wafer-level subgroups differs demonstrably from the value obtained by pooling sites, on generated data with a known spatial signature. This is the R-04 regression test. |
| `integration/` | Dialect differences, type coercion, and timezone behaviour across both databases. |
| `e2e/` | A re-measurement injected upstream resolves correctly and both rows survive to the processed zone. |

Every subgroup emitted in any test must carry a strategy; a contract test fails
if the field is absent.

## Documentation required

- `docs/api/preprocessing.md` — the stage contract and the repository port,
  with units, preconditions, and exceptions.
- `docs/domain/subgrouping.md` — why sites are not a rational subgroup, with the
  variance argument stated in full. This is the document a reviewer is pointed
  at when they ask why the platform charts wafer means.
- An ADR if the default subgrouping strategy is ever changed; it retroactively
  alters the meaning of every historical limit.
- Update `data/processed/README.md` with the published contract.

## Future extension points

- **Additional subgrouping strategies** — time-window, lot-based, or
  slot-stratified, declared in configuration behind the same recorded-strategy
  contract.
- **Additional unit families** — the registry is data, not code.
- **Polars migration** — confined to this module and Module 1, because analytics
  takes arrays ([TECH_STACK.md](../TECH_STACK.md) §10).
- **Alternative outlier flagging rules** — pluggable, provided the rule identity
  is recorded and nothing is removed.
- **Additional storage adapters** — one port, already contract-tested.

---

**Related:** [MODULE_DESIGN.md](../MODULE_DESIGN.md) ·
[01-data-ingestion.md](01-data-ingestion.md) ·
[03-spc-engine.md](03-spc-engine.md) ·
[DATASET_GUIDE.md](../DATASET_GUIDE.md)
