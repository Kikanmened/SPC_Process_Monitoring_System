# Module 5 — KPI and Trend Analysis

**Owning layers:** `analytics/kpi/`, `application/`
**Depends on:** Modules 3, 4, 6, 7, 10
**Depended on by:** Module 9
**Requirement coverage:** BO-5; FR-RP01 (summary reports). **Proposed and not approved:** FR-K01 – FR-K06
**Delivered in:** Phase 11 (aggregation), Phase 13 (trend reporting) · **Status:** Design — proposed scope, not approved

---

## Purpose

Answer the quality manager's question — where are the systemic issues, and is
the line getting better or worse? — by aggregating results the other modules
have already computed, across parameters, tools, areas, and time.

**This module computes no new statistic about a process.** It summarises
existing results. That constraint is the whole design: a trend view that decides
on its own when a value has "moved too far" is a second, unvalidated detector
sitting beside the audited one, and the two will eventually disagree in front of
an engineer. Detection stays in Modules 3 and 6; Module 5 describes.

### Scope status

The PRD names the quality manager persona and business objective BO-5, and
requires summary reports (FR-RP01), but defines no KPI set. The requirements
below are **proposed for approval and are not in the PRD**. Nothing may be built
against them until they are approved and the PRD is amended.

| Proposed | Requirement |
|---|---|
| FR-K01 | Define a fixed KPI set, each with a documented formula and unit |
| FR-K02 | Aggregate every KPI over configurable periods and dimensions: parameter, step, tool, chamber, product, area |
| FR-K03 | Report every KPI with sample size, window, and provenance; where data is insufficient, suppress the value and say so rather than extrapolating |
| FR-K04 | Report open excursion count and age distribution by severity |
| FR-K05 | Report recurrence: repeat excursions on the same characteristic, tool, or chamber within a configured window |
| FR-K06 | KPI and trend output is descriptive only; no KPI raises an alarm or produces a violation |

## Responsibilities

- Aggregate computed results into KPI values over a period and a dimension.
- Carry n, window, and provenance on every KPI value, exactly as a statistic
  must (NFR-U04).
- Suppress rather than estimate. A period with too few points yields a stated
  absence, never an interpolated point on a line.
- Compute period-over-period change and, where requested, a trend slope with its
  confidence interval and the method named. A slope without a stated method and
  interval is decoration.
- Report excursion aging, open counts by severity, and recurrence.
- Track the platform's own trust indicators over time: measured ARL₀ per rule
  set and detection performance from Module 6.
- Never emit a `Violation`, never write to the violation store, and never
  trigger a notification.

**Not this module's work:** deciding that a KPI movement is significant enough to
act on. That is either an SPC question — in which case the KPI itself belongs on
a control chart in Module 3 — or a human judgement.

## Public interfaces

```python
def aggregate_kpi(
    spec: KpiSpec,
    inputs: KpiInputs,
    window: TimeWindow,
    dimension: KpiDimension,
) -> KpiValue:
    """One KPI over one window and one grouping. Pure aggregation."""


def kpi_series(spec: KpiSpec, inputs: KpiInputs, periods: Sequence[TimeWindow]) -> KpiSeries:
    """A KPI over consecutive periods, with insufficient periods marked, never filled."""


def trend_slope(series: KpiSeries, method: TrendMethod) -> TrendEstimate:
    """Slope, confidence interval, and the method used. Descriptive; never a signal."""
```

| Exception | Raised when |
|---|---|
| `UnknownKpiError` | A requested KPI is not in the declared set; an unknown key is an error |
| `InsufficientDataError` | Below the configured minimum for the period — surfaced as suppression, not a filled value |
| `IncompatibleDimensionError` | The KPI is undefined for the requested grouping, for example gauge R&R by lot |

## Dependencies

| Depends on | For |
|---|---|
| Module 3 | Violation counts, measured ARL₀ per rule set |
| Module 4 | Capability and gauge R&R results over time |
| Module 6 | Detection performance metrics |
| Module 7 | Excursion records, dispositions, and closure state |
| Module 10 | KPI specifications, period configuration, provenance, audit |

Module 5 depends on results, never on raw measurements. If a KPI needs the
underlying series, that is a signal it belongs in Module 3 or 4 instead.

## Expected inputs

| Input | Source | Notes |
|---|---|---|
| Violation records | Violation repository | With severity, rule, timestamp, and disposition state |
| Capability and MSA results | Module 4 | Each already qualified with n, window, estimator |
| Detection performance | Module 6 | Scored against ground truth, with the dataset revision |
| Excursion records | Module 7 | Open, acknowledged, dispositioned, closed, with timestamps |
| KPI specifications | `configs/base/kpi.yaml` | Formula, unit, minimum n, permitted dimensions |

## Expected outputs

| Output | Consumer | Contents |
|---|---|---|
| `KpiValue` | Module 9 | Value, unit, n, window, dimension, provenance, or an explicit suppression reason |
| `KpiSeries` | Module 9 | Ordered periods with gaps preserved as gaps |
| `TrendEstimate` | Module 9 | Slope, confidence interval, method name, n |
| `ExcursionAgingSummary` | Module 9 | Open count and age distribution by severity |
| `RecurrenceSummary` | Module 9 | Repeat excursions by characteristic, tool, and chamber |

## Files to create

```
src/spc_platform/analytics/kpi/__init__.py
src/spc_platform/analytics/kpi/aggregation.py
src/spc_platform/analytics/kpi/trend.py               slope with interval and named method
src/spc_platform/analytics/kpi/recurrence.py
src/spc_platform/analytics/kpi/aging.py
src/spc_platform/domain/kpi.py                        KpiSpec, KpiValue, KpiSeries
src/spc_platform/application/use_cases/build_kpi_summary.py
configs/base/kpi.yaml                                 the declared KPI set
```

## Testing requirements

| Tier | What it must establish |
|---|---|
| `unit/` | Each aggregation against hand-computed values. A period below minimum n is suppressed with a reason, never filled or interpolated. An unknown KPI key raises. |
| `contract/` | Every `KpiValue` carries n, window, and provenance; the test fails if any is absent. **No code path in this module constructs a `Violation`** — asserted structurally, not by convention. |
| `statistical/` | The trend estimator recovers a known slope from generated data within its stated confidence interval, and reports no significant slope on flat data at the expected rate. |
| `integration/` | Aggregation over a realistic result volume across all supported dimensions. |

## Documentation required

- `docs/quality/kpi-definitions.md` — every KPI with its formula, unit,
  minimum n, valid dimensions, and what it does *not* mean. The last part
  matters: a rising violation count can mean a degrading process or a newly
  tightened rule set, and the definition must say so.
- `docs/api/kpi.md` — the aggregation contract.
- A PRD amendment adding FR-K01 – FR-K06 before implementation begins.

## Future extension points

- **Additional KPIs** — declared in configuration against the same qualification
  contract.
- **Cost-of-quality metrics** — scrap, rework, and hold time, once those records
  exist in the platform.
- **Benchmark comparison** across tools, areas, or sites, provided the
  comparison states its statistical test — at which point it belongs in
  Module 7's evidence contract rather than here.
- **OEE and equipment productivity** are deliberately excluded as features. The
  SEMI E79 vocabulary is aligned; the capability is out of scope (R-10).

---

**Related:** [MODULE_DESIGN.md](../MODULE_DESIGN.md) ·
[07-root-cause-analysis.md](07-root-cause-analysis.md) ·
[09-dashboard-and-reporting.md](09-dashboard-and-reporting.md) ·
[PRODUCT_REQUIREMENTS.md](../PRODUCT_REQUIREMENTS.md)
