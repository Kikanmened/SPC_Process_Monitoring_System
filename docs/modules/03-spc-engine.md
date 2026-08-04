# Module 3 — Statistical Process Control Engine

**Owning layers:** `analytics/charts/`, `analytics/rules/`, `analytics/estimators/`, `application/`
**Depends on:** Modules 2, 10
**Depended on by:** Modules 4, 6, 7, 8
**Requirement coverage:** FR-C01 – FR-C09, FR-R01 – FR-R06; NFR-P01, NFR-P07, NFR-C01 – NFR-C05
**Delivered in:** Phase 9 (analytics), Phase 11 (use case) · **Status:** Design — not implemented

---

## Purpose

The core of the product and the part its credibility rests on: given a
subgrouped series and a qualified baseline, compute the chart statistic, the
centre line, the control limits, the zone boundaries, and the set of run-rule
violations.

Everything in this module is pure. It holds no state between calls, never learns
which lot it is looking at, performs no I/O, and logs nothing — which is exactly
what makes it exhaustively testable against published references
([SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) §3.2).

The defects this module must not produce do not crash. A limit computed with the
wrong sigma estimator renders perfectly and is wrong by tens of percent; a run
rule with an off-by-one window signals slightly too often until operators stop
trusting alarms. Both are caught only by comparison against an authority outside
this codebase, which is why the statistical test tier exists.

## Responsibilities

- Compute plotted statistics and limits for I-MR, X̄-R, X̄-S, EWMA, CUSUM, and
  the p, np, c, and u attribute charts (FR-C01).
- Derive limits **only** from a qualified, approved baseline (FR-C03). The
  function signature requires a `Baseline`; there is no overload that computes
  limits from the series being charted.
- Select the chart type per parameter from control plan configuration, never
  from a global default (FR-C02).
- Compute 1σ, 2σ, and 3σ zone boundaries for rule evaluation (FR-C07).
- Evaluate Western Electric rules 1–4 and the Nelson eight-rule set, composable
  from shared primitives and configurable per parameter (FR-R01 – FR-R03).
- Record on every violation the rule identity, severity, chart, point, and
  timestamp (FR-R04).
- Expose EWMA λ and CUSUM k and h as per-parameter configuration (FR-C08).
- Measure and report ARL₀ for each configured rule set (FR-R05).
- Raise a typed error when no active baseline exists — never substitute a
  default limit (FR-C05, AC-A4).
- Keep every operation vectorised; a per-point Python loop misses the
  performance budget by roughly two orders of magnitude (NFR-P07).

**Not this module's work:** deciding *whether* a chart may be produced. Policy
lives in the application layer. Analytics computes what it is asked; the
application decides what may be asked.

## Public interfaces

```python
def limits_from_baseline(chart: ChartSpec, baseline: Baseline) -> ControlLimits:
    """Centre line, control limits, and zone boundaries, tagged with the estimator used."""


def plotted_series(subgroups: Sequence[Subgroup], chart: ChartSpec) -> PlottedSeries:
    """The statistic actually charted — individuals, subgroup mean, range, EWMA, CUSUM."""


def evaluate_rules(
    rule_set: RuleSet,
    series: PlottedSeries,
    limits: ControlLimits,
) -> Sequence[Violation]:
    """Apply a composed rule set over zoned data. Vectorised; no per-point loop."""


def measured_arl0(rule_set: RuleSet, simulation: InControlSimulation) -> ArlResult:
    """Average run length under an in-control process, for the configured rule set."""
```

Estimator constants (`d2`, `c4`, `A2`, `D3`, `D4`) live in
`analytics/estimators/` as cited functions, never inline. A `1.128` appearing in
a comparison is a defect ([CODING_STANDARDS.md](../CODING_STANDARDS.md) §8).

| Exception | Raised when |
|---|---|
| `NoActiveBaselineError` | Raised by the application when the baseline store has no approved active baseline. Carries the parameter. |
| `InsufficientDataError` | Fewer points than the chart requires; carries n and required n |
| `DegenerateSeriesError` | Zero-width limits — a constant series returns an error, never `inf` |
| `UnsupportedChartError` | The configured chart type does not apply to the parameter's data type |

## Dependencies

| Depends on | For |
|---|---|
| Module 2 | Subgroups carrying their strategy |
| Module 10 | Chart and rule set configuration, provenance, audit; injected clock in the use case only |
| `domain/` | `Baseline`, `ControlLimit`, `Violation`, `Subgroup`, `ChartSpec`, `RuleSet` |
| NumPy, SciPy, statsmodels | The only third-party libraries permitted in `analytics/` |

The application-layer use case additionally depends on the baseline store and
violation repository ports. Baselines are *read* here; they are created,
versioned, and superseded by Module 8.

## Expected inputs

| Input | Source | Notes |
|---|---|---|
| `Subgroup[]` | Module 2 | Each carries the subgrouping strategy that produced it |
| `Baseline` | Baseline store port | Immutable, approved, with n, estimator, effective date, approver |
| `ChartSpec` | `configs/spc/charts.yaml` via control plan | Chart type, sigma multiplier, EWMA λ, CUSUM k and h |
| `RuleSet` | `configs/spc/rule_sets.yaml` | Active rules for this parameter, with severities |
| `SpecificationLimit` | `data/reference/` | Passed for display only; never used to compute a control limit |

## Expected outputs

| Output | Consumer | Contents |
|---|---|---|
| `PlottedSeries` | Modules 6, 7, 9 | Plotted statistic per point with index, timestamp, and source subgroup |
| `ControlLimits` | Modules 4, 8, 9 | Centre line, UCL, LCL, zone boundaries, estimator name, baseline reference |
| `Violation[]` | Modules 6, 7, 9 | Rule identity, severity, chart, point index, timestamp |
| `ArlResult` | Modules 6, 8; `docs/validation/` | Measured ARL₀, simulation length, seed, theoretical comparison |
| `EvaluationResult` | Application callers | The above plus full provenance (FR-RP02) |

## Files to create

```
src/spc_platform/analytics/estimators/__init__.py
src/spc_platform/analytics/estimators/constants.py      d2, c4, A2, D3, D4 with citations
src/spc_platform/analytics/estimators/sigma.py          sigma_within, sigma_overall
src/spc_platform/analytics/charts/__init__.py
src/spc_platform/analytics/charts/individuals.py        I-MR
src/spc_platform/analytics/charts/xbar_r.py
src/spc_platform/analytics/charts/xbar_s.py
src/spc_platform/analytics/charts/ewma.py
src/spc_platform/analytics/charts/cusum.py
src/spc_platform/analytics/charts/attribute.py          p, np, c, u
src/spc_platform/analytics/charts/zones.py
src/spc_platform/analytics/rules/__init__.py
src/spc_platform/analytics/rules/primitives.py          vectorised run, trend, zone tests
src/spc_platform/analytics/rules/western_electric.py
src/spc_platform/analytics/rules/nelson.py
src/spc_platform/analytics/rules/rule_set.py            composition and severity
src/spc_platform/analytics/rules/arl.py                 ARL measurement over simulated series
src/spc_platform/domain/control_limit.py
src/spc_platform/domain/baseline.py
src/spc_platform/domain/violation.py
src/spc_platform/domain/chart_spec.py
src/spc_platform/application/use_cases/evaluate_lot.py
src/spc_platform/application/ports/baseline_store.py
src/spc_platform/application/ports/violation_repository.py
src/spc_platform/infrastructure/repositories/baseline_store.py
src/spc_platform/infrastructure/repositories/violation_repository.py
configs/spc/charts.yaml
configs/spc/rule_sets.yaml
```

## Testing requirements

This module carries the heaviest testing obligation in the project. All five
verification methods in [TESTING_STRATEGY.md](../TESTING_STRATEGY.md) §3 apply.

| Tier | What it must establish |
|---|---|
| `statistical/` | Every chart family reproduces published worked examples from NIST/SEMATECH and Montgomery, expected values cited to table or example number. Hand-computed cases cover what no textbook tabulates: minimum subgroup sizes, boundary n. |
| `statistical/` (invariants) | Under Hypothesis: limits are scale- and shift-equivariant; EWMA with λ = 1 reduces exactly to an individuals chart; a constant series raises `DegenerateSeriesError`; rule evaluation is invariant to sign flip about the centre line. |
| `statistical/` (simulation) | Measured ARL₀ within ±15% of theory for each configured rule set — approximately 370 for the single 3σ rule and approximately 91.75 for the four Western Electric rules combined, per [TESTING_STRATEGY.md](../TESTING_STRATEGY.md) §3.4. Seeded and deterministic. |
| `statistical/` (ground truth) | Detection rate ≥ 95% at 1.5σ and ≥ 99% at 3σ against injected faults, with localisation within ±3 points ≥ 80%. |
| `unit/` | Every refusal path, including the absent baseline, which must raise rather than draw. |
| `performance/` | 1 000 points with limits and the full rule set under 50 ms (NFR-P01). |

Snapshotting current output as an expected value is prohibited in this tier; it
freezes whatever defect exists today and makes it permanent.

## Documentation required

- `docs/api/spc-engine.md` — every public function with parameters, units,
  preconditions, exceptions, and references.
- `docs/validation/` — the reference case results, measured ARL₀ per rule set,
  and the detection scorecard. This is the documentary answer to "how do you
  know your limits are right?"
- An ADR for any change to a sigma estimator or a rule definition, because it
  retroactively alters the meaning of every historical number.
- Update `configs/spc/README.md` when a new chart type or rule becomes
  configurable.

## Future extension points

- **New chart type** — implement in `analytics/charts/`, register in
  `configs/spc/`; no change to the application or the UI
  ([SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) §8).
- **New rule set** — declared in configuration; the primitives compose. Any new
  set must arrive with its measured ARL₀ (FR-R06).
- **Variable control limits** for attribute charts with unequal subgroup sizes —
  the limits object already carries per-point values.
- **Multivariate SPC** (Hotelling T², PCA) — an additional analytics module
  consuming the same subgrouped input, gated behind Phase 15.
- **Equipment state overlay** (FR-C09) — the plotted series carries timestamps;
  the E10 state history joins in the view layer, not here.

---

**Related:** [MODULE_DESIGN.md](../MODULE_DESIGN.md) ·
[02-data-preprocessing.md](02-data-preprocessing.md) ·
[06-anomaly-detection.md](06-anomaly-detection.md) ·
[TESTING_STRATEGY.md](../TESTING_STRATEGY.md)
