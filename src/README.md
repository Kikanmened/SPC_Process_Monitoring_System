# `src/` — Application Source

## Why this folder exists

All importable, testable, shippable Python lives here and nowhere else. The
repository uses a **src layout** (`src/spc_platform/`) rather than a top-level
package for one reason that matters in a regulated manufacturing context: it is
impossible to accidentally import the package from the working directory. Tests
run against the *installed* distribution, so what CI validates is byte-identical
to what a fab engineer would deploy. A test suite that passes only because the
repository root happens to be on `sys.path` has validated nothing.

Everything else in this repository — dashboards, notebooks, scripts, reports —
is a *consumer* of `spc_platform`. None of them may contain business logic.

## Layout

```
src/spc_platform/
├── domain/           Pure business model. No I/O, no frameworks.
├── application/      Use cases that orchestrate domain objects.
├── analytics/        The SPC / statistics engine.
├── pipelines/        Ingest → validate → transform → publish flows.
├── infrastructure/   Adapters to the outside world.
├── api/              HTTP surface (FastAPI).
├── cli/              Operator and batch entry points.
├── config/           Typed settings loading and validation.
├── observability/    Logging, metrics, tracing, audit trail.
└── common/           Cross-cutting primitives with no domain meaning.
```

## What belongs in each layer

### `domain/`
The vocabulary of wafer fabrication, modelled as types: `Lot`, `Wafer`,
`Site`, `MeasurementPoint`, `ProcessStep`, `ToolChamber`, `Recipe`,
`SpecificationLimit`, `ControlLimit`, `Violation`, `ControlChartType`.

This layer has **zero dependencies** on pandas, on the database, on the
dashboard, or on any config file. It is where invariants are enforced: a
`SpecificationLimit` cannot have `lsl > usl`; a control limit must be derived
from a qualified baseline, never typed in by a user. Because it is pure, it is
the cheapest layer to test exhaustively and the one an AI agent can reason
about without loading the rest of the repository.

**Critical distinction encoded here:** specification limits come from the
customer or the device spec; control limits come from the process itself.
Conflating them is the most common and most expensive error in SPC tooling, so
they are separate types that cannot be substituted for one another.

### `application/`
Use cases, one per meaningful engineering action: "evaluate a lot against its
control plan", "recompute baseline limits for a parameter", "acknowledge an
out-of-control event", "generate a capability report for a process window".

Use cases depend on domain types and on *ports* (interfaces), never on concrete
adapters. This is what makes the platform testable without a database and
portable across a real MES and a simulator.

### `analytics/`
The statistical core, and the part of this repository that must be correct
beyond argument:

- **Control charts** — I-MR, X̄-R, X̄-S, EWMA, CUSUM, and attribute charts
  (p, np, c, u).
- **Run rules** — Western Electric and Nelson rule sets, configurable per
  parameter because a rule set appropriate for a CMP thickness measurement is
  not appropriate for a defect count.
- **Capability** — Cp, Cpk, Pp, Ppk, Cpm, with explicit short-term versus
  long-term sigma estimation, because reporting Cpk computed from overall
  sigma is a silent misstatement of process performance.
- **MSA / Gauge R&R** — measurement system analysis, since a chart built on an
  unqualified gauge measures the metrology tool, not the process.
- **Distribution work** — normality testing, transformation, and non-normal
  capability, which is the common case for particle counts and etch defects.

Functions here are pure and vectorised: data in, results out. No logging of
business events, no database access, no chart rendering. This is what allows
the statistical test suite (`tests/statistical/`) to validate the engine
against published reference datasets and hand-computed cases.

### `pipelines/`
The path measurement data takes from a raw fab export to a chartable series:
ingestion, schema validation, unit normalisation, outlier and re-measurement
handling, lot/wafer/site aggregation, and publication. Each stage is
independently testable and each stage records lineage. When a chart looks
wrong at 03:00, the question "which transformation did this?" must have a
one-command answer.

### `infrastructure/`
Every adapter that touches something outside this process: databases, object
storage, MES/YMS clients, SECS/GEM or equipment-data feeds, file readers for
fab export formats, notification transports. Third-party quirks are contained
here so they never leak into the domain or the analytics engine.

### `api/`
A thin HTTP layer. Route handlers parse the request, call one use case, and
serialise the result. If a handler contains an `if` statement about process
behaviour, that logic is in the wrong file.

### `cli/`
Entry points for scheduled jobs, backfills, baseline recalculation, and
operator tooling. The CLI and the API are two front doors onto the same use
cases — never two implementations of the same behaviour.

### `config/`
Typed, validated settings objects. Configuration is *parsed once at the
boundary* into immutable objects; the rest of the codebase receives typed
values and never reads a YAML file or an environment variable directly.

### `observability/`
Structured logging, metrics, tracing, and — separately — the **audit trail**.
Operational logs and audit records are different things with different
retention and integrity requirements, and they are kept apart deliberately.

### `common/`
Genuinely generic helpers: result types, time handling, unit conversion
primitives. Guarded strictly. `common/` is where architecture goes to die if
anything domain-shaped is allowed in.

## Dependency rule

Dependencies point inward, and only inward:

```
api / cli / dashboard  →  application  →  domain
                              ↓              ↑
                       infrastructure   analytics
```

`domain` imports nothing from this repository. `analytics` imports only
`domain` and `common`. If a proposed import violates this direction, the
design is wrong — not the rule.

## Conventions

- Full type annotations; `mypy --strict` is the gate, not a suggestion.
- Public functions carry docstrings that state units, assumptions, and — for
  statistical functions — the reference the implementation follows.
- No module-level side effects. Importing `spc_platform` must not open a
  connection, read a file, or configure logging.
- Any statistical function states its estimator explicitly. "Sigma" without a
  qualifier is not acceptable in this codebase.
