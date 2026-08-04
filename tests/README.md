# `tests/` — Verification Suite

## Why this folder exists

In a manufacturing quality tool, the test suite *is* the product's credibility.
A control chart that silently miscomputes a limit does not crash — it lets
scrap through, or it halts a healthy tool. Neither failure announces itself.
The only defence is a suite that proves the statistics are right, the pipeline
is faithful, and the alarm logic fires exactly when it should.

Tests are separated by **what kind of confidence they buy**, not by which
source file they happen to touch. Splitting this way lets both engineers and
the AI agent run the fast, high-signal subset on every change and reserve the
slow subset for CI.

## Layout

```
tests/
├── unit/          Fast, isolated, no I/O. The bulk of the suite.
├── integration/   Real adapters: database, file formats, MES client.
├── e2e/           Full path from raw export to rendered chart and alarm.
├── statistical/   Numerical correctness of the SPC engine.
├── contract/      Schema and API compatibility guarantees.
├── performance/   Throughput and latency budgets on fab-scale volumes.
├── fixtures/      Static reference data and golden files.
└── factories/     Programmatic builders for domain objects.
```

## `statistical/` — the layer that makes this project credible

This is the differentiator and the reason this folder is not merged into
`unit/`. It validates the analytics engine against sources that are
independent of this implementation:

- **Published reference datasets** — NIST/SEMATECH engineering statistics
  handbook cases, and textbook examples (Montgomery) with documented expected
  values. These two are the *only* sources of numerical expectations; AIAG and
  SEMI publications govern terminology and methodology but never supply a
  number (ADR-0017).
- **Hand-computed cases** — small datasets where control limits and capability
  indices are worked out by hand in the test docstring, so a reviewer can
  verify the expectation without trusting the code.
- **Analytical properties** — invariants that must hold regardless of input:
  Cp ≥ Cpk always; an EWMA with λ = 1 reduces to an individuals chart; a
  constant series produces zero-width control limits and must be handled, not
  divided by.
- **Property-based tests** — Hypothesis-generated series asserting that
  estimators are scale- and shift-equivariant where theory says they must be.
- **False-alarm rate verification** — simulated in-control processes confirming
  that the configured run-rule set produces the expected ARL. A rule set that
  fires ten times more often than theory predicts destroys operator trust in
  the system, and that is a defect even though every individual unit test
  passes.

Every numerical expectation in this folder cites its source. "Expected 1.33
because that is what the function returned" is not a test; it is a snapshot of
a possible bug.

## `contract/`

Guards the boundaries that other systems depend on: ingestion schemas, API
response shapes, exported report structures. A control chart that changes its
JSON field names without warning breaks every downstream consumer. These tests
fail loudly on any unversioned boundary change.

## `performance/`

A fab generates measurement data continuously, and a wafer map is 25 wafers ×
dozens of sites × many parameters per lot. Chart computation that is elegant
but linear-per-point falls over at production volume. This folder pins
explicit budgets so regressions surface in CI rather than on a shift lead's
screen.

## `fixtures/` and `factories/`

- `fixtures/` holds static, reviewable artefacts: reference CSVs, golden
  chart outputs, sample fab exports with known defects deliberately embedded.
- `factories/` holds builders (`a_lot().with_drift(...)`) so tests describe
  the *scenario* rather than the plumbing. A test named
  `test_detects_gradual_drift_before_spec_violation` should read like the
  engineering claim it makes.

## Conventions

- Test names state the behaviour and the expectation, not the function name.
- One assertion concept per test; a test that checks five things reports its
  failure ambiguously.
- No network access and no wall-clock dependence in `unit/`. Time is injected.
- Coverage is a diagnostic, not a target. `analytics/` and `domain/` are held
  near-exhaustive; a coverage percentage on the repository as a whole is a
  vanity number.
- Every fixed defect earns a regression test that fails against the old code.
