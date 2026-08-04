# Testing Strategy

**Document owner:** Project lead
**Status:** Active — strategy fixed; tiers stand up from Phase 6, statistical
tier populated in Phase 9
**Last updated:** 2026-08-03

---

## 1. What we are defending against

In most software, a defect announces itself: an exception, a failed request, a
blank screen. In a statistical process control platform, the defects that
matter do none of that.

A control limit computed with the wrong sigma estimator produces a chart that
renders perfectly, looks entirely plausible to an experienced engineer, and is
wrong by 40%. A run rule with an off-by-one window signals slightly too often —
not obviously, just enough that operators gradually stop trusting alarms. A
capability index computed on an out-of-control process yields a confident 1.45
describing a distribution that does not exist.

**None of these crash. None fail a conventional unit test written against the
implementation.** They are caught only by comparing against an authority
outside the codebase, or by measuring statistical behaviour over many runs.
That is what this strategy is built around, and it is why
`tests/statistical/` exists as a separate tier rather than as a subfolder of
`tests/unit/`.

## 2. Test tiers

Organised by **the kind of confidence each buys**, not by which source file it
touches. This lets both engineers and the AI agent run the fast, high-signal
subset on every change and reserve the slow subset for CI.

| Tier | Question it answers | Speed | Volume | Gate |
|---|---|---|---|---|
| `unit/` | Does this unit behave as specified? | < 5 s total | ~60% of tests | Pre-commit |
| `statistical/` | Are the numbers actually correct? | < 60 s | ~20% | Pre-commit + own CI stage |
| `integration/` | Do the adapters work against real dependencies? | < 3 min | ~10% | CI |
| `contract/` | Are our boundaries still compatible? | < 30 s | ~5% | CI |
| `e2e/` | Does the whole path work? | < 5 min | ~3% | CI |
| `performance/` | Do we still meet the budgets? | < 2 min | ~2% | CI (nightly full run) |

Target overall runtime: **under 5 seconds for the pre-commit subset**. A test
suite slow enough to skip is a test suite that gets skipped, and then the gate
is decorative.

## 3. The statistical tier

This is the tier that makes the project credible. Five distinct verification
methods, because no single one catches everything.

### 3.1 Published reference datasets

Expected values come from sources independent of this implementation. Which
sources is governed by the three-layer reference hierarchy in
[ADR-0017](DECISION_LOG.md#adr-0017):

| Layer | Purpose | Authority | Numerical test dependency? |
|---|---|---|---|
| 1 | Mathematical correctness | NIST/SEMATECH e-Handbook; Montgomery, 8th ed. | **Yes — exclusively** |
| 2 | Industrial quality alignment | AIAG SPC / MSA, IATF 16949, VDA | No |
| 3 | Semiconductor relevance | SEMI standards — E10, E79, E90, E120/E125, E142, E148, SECS/GEM, EDA | No |

**Only Layer 1 supplies numerical expectations.**

- **NIST/SEMATECH e-Handbook of Statistical Methods** — worked examples with
  published intermediate and final values.
- **Montgomery, *Introduction to Statistical Quality Control*, 8th ed.** — the
  standard text; chapter examples with tabulated results.

Both are publicly accessible, which is the point. An expected value a reviewer
cannot look up is not a citation, it is a claim — and a verification anyone can
reproduce is worth more than one behind a paywall. Having two independent
sources also lets them check each other where their examples overlap.

**AIAG and SEMI publications are never cited for a numerical expectation.**
They are copyrighted commercial standards, and reproducing worked-example data
from them would carry a licensing exposure this project has no reason to take.
Their role is Layer 2 and Layer 3: AIAG governs terminology, %GRR and NDC
acceptance bands, and control plan structure; SEMI governs the equipment model,
equipment state semantics, substrate and timestamp conventions, and interface
design ([domain/SEMI_STANDARDS_ALIGNMENT.md](domain/SEMI_STANDARDS_ALIGNMENT.md)).
Both shape *what the code means*, neither supplies *what a test asserts*.

Every expected value cites its source, including the table or example number.

```python
def test_xbar_r_limits_match_montgomery_example_6_1() -> None:
    """X-bar/R limits for the piston ring data.

    Montgomery (2019), 8th ed., Example 6.1: 25 subgroups of n=5,
    x_bar_bar = 74.001, R_bar = 0.023.
    Published limits: UCL = 74.014, LCL = 73.988 (A2 = 0.577).
    """
```

### 3.2 Hand-computed cases

Small datasets where the arithmetic is worked out in the docstring, so a
reviewer can verify the expectation without executing anything and without
trusting the author. These cover the cases no textbook tabulates: subgroup size
boundaries, minimum viable n, single-sided specifications.

### 3.3 Analytical invariants

Properties that must hold for any input, checked with **Hypothesis**:

- `Cp >= Cpk` always, for every input. If this ever fails, one of the two is
  wrong regardless of what the reference tables say.
- EWMA with λ = 1 reduces exactly to an individuals chart.
- Control limits are **scale- and shift-equivariant**: multiply every
  measurement by 2 and add 10, and the limits transform identically. This
  single property catches a large class of estimator errors.
- A constant series produces zero-width limits and must raise
  `DegenerateSeriesError`, not return `inf`.
- Rule evaluation is invariant to sign flip about the centre line.
- `sigma_within <= sigma_overall` for any series containing between-subgroup
  drift.

### 3.4 Simulation-based verification

Some statistical properties exist only in aggregate and cannot be tested on a
single dataset.

**False-alarm rate (ARL₀).** Simulate a long in-control normal process,
evaluate the configured rule set, measure the average run length, and assert it
falls within tolerance of theory: ≈ 370 for the single 3σ rule, ≈ 91.75 for the
four Western Electric rules combined. **A rule set firing far more often than
theory predicts destroys operator trust, and that is a defect even though every
unit test passes.**

**Detection power (ARL₁).** Inject a known shift and measure how many points
until detection. Asserts the claim the platform makes about itself: EWMA
detects a 1σ shift substantially faster than a Shewhart chart.

Seeded, so the tests are deterministic despite being stochastic. Tolerances
derived from the theoretical distribution of the run length, not chosen to make
the test pass.

### 3.5 Ground-truth scoring against injected faults

The reason `data/synthetic/` and `scripts/simulation/` are load-bearing rather
than convenient. Because injected faults have **known ground truth** — the exact
point where a drift began, the size of a step shift, the tool that degraded —
the engine can be *scored* rather than inspected:

| Metric | Meaning | Acceptance |
|---|---|---|
| Detection rate | Fraction of injected faults detected | ≥ 95% for shifts ≥ 1.5σ |
| Detection latency | Points from fault onset to first signal | Within theoretical ARL₁ + tolerance |
| False-alarm rate | Signals on clean, in-control segments | Within the configured rule set's ARL₀ |
| Localisation | Fraction where the signalling point is within ±3 of onset | ≥ 80% |

A real-data project could not make these claims. This is the strongest
argument the project makes about its own correctness, and it is only available
because the data is synthetic.

## 4. The other tiers

**`unit/`** — Fast and isolated. No network, no filesystem, no database, no
wall-clock dependence (time is injected). Domain invariants, use case policy
with fake adapters, pipeline stage behaviour in isolation.

**`integration/`** — Real adapters against real dependencies: DuckDB and
PostgreSQL in containers, actual Parquet and CSV round-trips, Alembic
migrations applied forward and rolled back. Catches what mocks hide — dialect
differences, type coercion, timezone handling on the wire.

**`contract/`** — Two directions. *Port contracts*: one shared test suite that
every implementation of a port must pass, so the in-memory fake used in unit
tests is provably equivalent to the real repository. *Boundary contracts*:
ingestion schemas, API responses against the OpenAPI schema, and export
formats, so a renamed column fails here rather than silently in a downstream
system.

**`e2e/`** — The full path: generate synthetic data with a known injected
fault, run ingestion, evaluate against the control plan, confirm the expected
violation appears, acknowledge it, and confirm the audit record exists. One
scenario per critical user journey, no more — e2e tests are expensive and
brittle in proportion to their number.

**`performance/`** — Asserts the budgets in
[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §7 with `pytest-benchmark`.
Fails on regression beyond a threshold rather than on absolute timing, since
absolute numbers vary by machine.

## 5. Fixtures and factories

**`fixtures/`** holds static, reviewable artefacts: reference CSVs from the
cited publications, golden outputs, sample fab exports with deliberately
embedded defects.

**`factories/`** holds builders so tests describe the scenario rather than the
plumbing:

```python
series = (
    a_parameter_series()
    .in_control(mean=250.0, sigma=2.5, n=100)
    .with_step_shift(at_point=60, magnitude_sigma=1.5)
    .build()
)
```

A test named `test_detects_gradual_drift_before_specification_violation` should
read like the engineering claim it makes. Test setup that obscures the scenario
defeats the purpose of writing the test.

## 6. Coverage policy

Coverage is a **diagnostic, not a target**. A repository-wide percentage is a
vanity number that averages critical code together with glue.

| Area | Expectation |
|---|---|
| `domain/` | Near-exhaustive; every invariant has a test that violates it |
| `analytics/` | Near-exhaustive, plus the statistical tier above |
| `application/` | All use case paths including refusal paths |
| `pipelines/` | All stages, all validation failure modes |
| `infrastructure/` | Contract tests; not line coverage of driver code |
| `dashboard/` | Interaction smoke tests; visual review is the real gate |

CI reports coverage and fails on a **drop** in `domain/` or `analytics/`, not
on an absolute number elsewhere.

## 7. What we deliberately do not test

- **Third-party library internals.** NumPy's mean is not our concern; our use
  of it is.
- **Exact pixel output.** Visual regression on charts is brittle and
  low-signal. Chart *data* is asserted; appearance is reviewed by a human.
- **Streamlit framework behaviour.** We test our callbacks and our data, not
  the framework's rendering.
- **Generated documentation.** Link validity is checked; prose is not.

## 8. Test-writing rules

1. **One behaviour per test.** A test asserting five things reports its failure
   ambiguously.
2. **Name the behaviour, not the function.**
   `test_cpk_below_target_when_process_off_centre`, not `test_cpk_2`.
3. **Never snapshot current output as the expectation** in the statistical
   tier. That freezes whatever bug exists today and makes it permanent.
4. **Every fixed defect earns a regression test that fails against the old
   code.** Verify it fails before the fix, or it may be testing nothing.
5. **No sleeping, no real clocks, no network** outside `integration/`.
6. **Seed every stochastic test** and record the seed in the failure message.
7. **Assert on refusals as well as results.** That the system *declines* to
   produce a capability index for an out-of-control process is a requirement,
   and it needs a test.

## 9. CI gating

Stages run fastest-failing first, so a formatting error never consumes a full
test run:

```
lint/format → type check → unit → statistical → contract → integration → e2e → performance → security
```

**`statistical` is a separately reported stage.** A failure there must be
unmistakable in the run summary rather than buried among hundreds of passing
unit tests, because it means a number the platform produces is wrong.

Merges to `main` require: every stage green, no coverage drop in `domain/` or
`analytics/`, and — for any change touching statistical behaviour — an explicit
statement in the pull request of whether existing baselines or reports are
invalidated.

---

**Related:** [CODING_STANDARDS.md](CODING_STANDARDS.md) ·
[QUALITY_ASSURANCE_PLAN.md](QUALITY_ASSURANCE_PLAN.md) ·
[DATASET_GUIDE.md](DATASET_GUIDE.md) ·
[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
