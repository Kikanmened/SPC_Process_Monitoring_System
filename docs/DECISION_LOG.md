# Decision Log

**Document owner:** Project lead
**Status:** Active
**Last updated:** 2026-08-04

Architecture Decision Records. Each entry states the context, the decision, the
alternatives rejected, and the consequences — including the negative ones,
which are the part most often omitted and the part most worth having later.

**Records are immutable.** A decision that changes is superseded by a new
record, never rewritten. The history of *why* is worth more than a tidy current
state, and "why is it done this way?" is the question that otherwise costs an
afternoon of code archaeology.

Detailed records for significant future decisions go in `docs/adr/` as numbered
files; this log is the index and holds the foundational decisions made during
Phases 1–5.

| ID | Decision | Status | Date |
|---|---|---|---|
| [ADR-0001](#adr-0001) | src layout with `pyproject.toml` | Accepted | 2026-08-03 |
| [ADR-0002](#adr-0002) | Hexagonal architecture with inward-only dependencies | Accepted | 2026-08-03 |
| [ADR-0003](#adr-0003) | Specification and control limits as distinct types | Accepted | 2026-08-03 |
| [ADR-0004](#adr-0004) | Statistical validation as a separate test tier | Accepted | 2026-08-03 |
| [ADR-0005](#adr-0005) | Implement SPC mathematics in-house | Accepted | 2026-08-03 |
| [ADR-0006](#adr-0006) | Streamlit for the dashboard | Accepted | 2026-08-03 |
| [ADR-0007](#adr-0007) | uv for environment and dependency management | Accepted | 2026-08-03 |
| [ADR-0008](#adr-0008) | DuckDB locally, PostgreSQL + TimescaleDB in production | Accepted | 2026-08-03 |
| [ADR-0009](#adr-0009) | Declarative process configuration | Accepted | 2026-08-03 |
| [ADR-0010](#adr-0010) | Synthetic data with injected faults as the primary dataset | Accepted | 2026-08-03 |
| [ADR-0011](#adr-0011) | Audit trail separate from operational logging | Accepted | 2026-08-03 |
| [ADR-0012](#adr-0012) | Arrays in the analytics layer, DataFrames at the boundaries | Accepted | 2026-08-03 |
| [ADR-0013](#adr-0013) | Modular monolith, not microservices | Accepted | 2026-08-03 |
| [ADR-0014](#adr-0014) | On-premises deployment assumption | Accepted | 2026-08-03 |
| [ADR-0015](#adr-0015) | Documentation before implementation | Accepted | 2026-08-03 |
| [ADR-0016](#adr-0016) | Python 3.13 pinned exactly, single supported version | Accepted | 2026-08-04 |
| [ADR-0017](#adr-0017) | Three-layer reference hierarchy for validation and terminology | Accepted | 2026-08-04 |
| [ADR-0018](#adr-0018) | Interactive Plotly wafer maps; static images for export only | Accepted | 2026-08-04 |
| [ADR-0019](#adr-0019) | Modules are capability slices, not packages | Accepted | 2026-08-04 |
| [ADR-0020](#adr-0020) | One gate script for local and CI | Accepted | 2026-08-04 |

---

<a id="adr-0001"></a>
## ADR-0001 — src layout with `pyproject.toml`

**Status:** Accepted · 2026-08-03

**Context.** A Python project may place its package at the repository root
(flat layout) or under `src/`. With a flat layout the package is importable
from the working directory, which means tests may pass because the repository
root happens to be on `sys.path` rather than because the package installs and
works.

**Decision.** src layout, `src/spc_platform/`, with PEP 621 metadata in
`pyproject.toml`. Tests run against the installed distribution.

**Alternatives rejected.** Flat layout — simpler, and it permits exactly the
failure above. `setup.py` — superseded.

**Consequences.** Positive: CI validates what deploys; import shadowing is
impossible; packaging is a solved problem from day one. Negative: an editable
install is required before tests run, which is one extra step for a newcomer.
In a context where an analysis must be reproducible to be defensible, that
trade is not close.

---

<a id="adr-0002"></a>
## ADR-0002 — Hexagonal architecture with inward-only dependencies

**Status:** Accepted · 2026-08-03

**Context.** The statistical engine must be testable without infrastructure,
and the data source is guaranteed to change — synthetic Parquet during
development, a fab MES in any realistic deployment.

**Decision.** Ports and adapters. `domain/` and `analytics/` at the centre with
no outward dependencies; `application/` defines ports; `infrastructure/`
implements them; `dashboard/`, `api/`, and `cli/` are interchangeable front
doors. Enforced mechanically by `import-linter` in CI.

**Alternatives rejected.** Layered n-tier — familiar, but tends to leak
persistence concerns into business logic. A pragmatic "just organise it
sensibly" approach — which depends on discipline that no single contributor
sustains across months, and which an AI contributor cannot infer at all.

**Consequences.** Positive: verifying a Cpk calculation needs no database
fixture; swapping the data source touches one adapter and zero statistical
lines; the boundaries are explicit enough for an agent to follow. Negative:
more indirection than a project of this size would otherwise need, and port
definitions add ceremony. Accepted because the two properties above are
precisely the ones this project cannot do without.

---

<a id="adr-0003"></a>
## ADR-0003 — Specification and control limits as distinct types

**Status:** Accepted · 2026-08-03

**Context.** Specification limits come from the device requirement and state
what is acceptable. Control limits are derived from the process and state what
it normally does. Conflating them is the most common serious error in SPC
tooling: a chart drawn with spec limits as control limits cannot detect a shift
until material is already non-conforming.

**Decision.** `SpecificationLimit` and `ControlLimit` are structurally
distinct types with no conversion between them and no shared base class
exposing a generic `.limits` accessor. The type checker rejects substitution.
The dashboard renders them with visually distinct, non-interchangeable
treatments.

**Alternatives rejected.** A single `Limit` type with a `kind` field —
convenient, and it makes the error a runtime possibility that testing must
chase. Convention and review — the error is subtle enough to survive review,
which is exactly why it is so widespread.

**Consequences.** Positive: the defining error of bad SPC tooling cannot be
expressed in this codebase. It becomes a compile-time impossibility rather than
a code-review responsibility. Negative: some duplication between the two types,
and any code handling both needs two paths. Trivial cost for the guarantee.

---

<a id="adr-0004"></a>
## ADR-0004 — Statistical validation as a separate test tier

**Status:** Accepted · 2026-08-03 · *Reference sources narrowed by
[ADR-0017](#adr-0017)*

**Context.** Statistical defects do not crash. A wrong sigma estimator renders
a perfect chart that is wrong by 40%. Conventional unit tests written against
the implementation cannot catch this, because they encode the same
misunderstanding.

**Decision.** `tests/statistical/` as a distinct tier with its own CI stage.
Expected values come from external references (NIST/SEMATECH, Montgomery, AIAG),
hand-computed cases, analytical invariants under Hypothesis, and
simulation-based ARL verification. **Snapshotting current output as the
expected value is prohibited** — it freezes whatever bug exists today.

**Alternatives rejected.** Folding these into `tests/unit/` — a failure would
be buried among hundreds of passing tests, when it means a number the platform
produces is wrong. Manual verification in notebooks — not repeatable, not
gating.

**Consequences.** Positive: the project can substantiate its central claim
rather than assert it; a reviewer can check any expected value against its
cited source. Negative: writing these tests is slow and requires locating
reference values, which meaningfully constrains the pace of the analytics
phase. That is the correct constraint.

---

<a id="adr-0005"></a>
## ADR-0005 — Implement SPC mathematics in-house

**Status:** Accepted · 2026-08-03

**Context.** Third-party Python SPC packages exist and would save
considerable time.

**Decision.** Implement control charts, capability, MSA, and variance
decomposition directly on NumPy, SciPy, and statsmodels.

**Alternatives rejected.** An existing SPC library — it would remove the
substance being demonstrated, and none of the available options carries
validation evidence adequate for the claims this project makes. Commercial
software — not inspectable.

**Consequences.** Positive: full control over estimator choice and its
documentation; every formula is citable and verified; the implementation *is*
the portfolio. Negative: substantially more work, and the correctness burden
sits entirely with this project — which is why ADR-0004 exists. Note that the
*numerical primitives* are not reimplemented: NumPy, SciPy, and statsmodels do
the arithmetic, and only the SPC-specific layer is ours.

---

<a id="adr-0006"></a>
## ADR-0006 — Streamlit for the dashboard

**Status:** Accepted · 2026-08-03

**Context.** The interface is for process and quality engineers, not consumers.
It must be quick to build, readable by a Python-literate engineer, and
maintainable by one person.

**Decision.** Streamlit with Plotly charts, confined behind the `dashboard/`
boundary with zero statistical logic.

**Alternatives rejected.** Dash — finer layout control at meaningfully higher
build cost. React + FastAPI — unjustifiable for this audience and this team
size. Panel — smaller ecosystem.

**Consequences.** Positive: fastest path from a verified engine to a usable
interface; a process engineer can read and extend it. Negative: real
constraints on layout and session state, which may bite on the wafer map and
the alarm queue (see R-42). Mitigated structurally: because the dashboard is a
client of the application layer, replacing it touches presentation only.

---

<a id="adr-0007"></a>
## ADR-0007 — uv for environment and dependency management

**Status:** Accepted · 2026-08-03

**Context.** A reproducible environment is a precondition for a defensible
analysis. The scientific Python ecosystem has historically used conda for this.

**Decision.** uv, with a committed `uv.lock` and `--frozen` production
installs.

**Alternatives rejected.** conda/mamba — the traditional choice, now
unnecessary since PyPI wheels for the numerical stack are reliable; slow and
heavy by comparison. Poetry — good, considerably slower, and does not manage
Python versions. pip + requirements.txt — insufficient locking.

**Consequences.** Positive: 10–100× faster resolution; one tool manages the
Python toolchain, the environment, and the lockfile; byte-reproducible
environments. Negative: a younger tool than the alternatives, so ecosystem
maturity is a real if diminishing consideration. The lockfile format is
portable enough that reversing this decision is cheap.

---

<a id="adr-0008"></a>
## ADR-0008 — DuckDB locally, PostgreSQL + TimescaleDB in production

**Status:** Accepted · 2026-08-03

**Context.** Two conflicting requirements. A reviewer must be able to clone the
repository and see working charts within minutes, with no infrastructure. A
realistic deployment must handle 10⁷–10⁸ time-series records with heavy
relational context.

**Decision.** Both, behind a single repository port. DuckDB with Parquet for
the local profile; PostgreSQL 16 with TimescaleDB for production. SQLAlchemy 2.0
Core for dialect portability; Alembic for migrations.

**Alternatives rejected.** SQLite — row-oriented and poor at analytical scans.
A pure time-series database (InfluxDB) — handles the time series well and the
relational context badly, and measurement data is deeply relational: lot, wafer,
slot, tool, chamber, recipe, route. PostgreSQL only — requires a running server
for the "clone and run" case, which defeats it.

**Consequences.** Positive: zero-setup local experience and a production-grade
path, with one port and one contract test suite covering both. Negative: two
dialects to keep compatible, and dialect differences must be caught by
integration tests rather than assumed away.

---

<a id="adr-0009"></a>
## ADR-0009 — Declarative process configuration

**Status:** Accepted · 2026-08-03

**Context.** In a fab, process knowledge changes far more often than code. New
tools are qualified, limits recalculated, rule sets tuned. If that knowledge is
embedded in Python, every process change becomes a release — and the people who
own the decision cannot make it.

**Decision.** Chart selection, rule sets, tool and parameter registries,
specification limits, and control plans live in `configs/` and
`data/reference/` as validated YAML, versioned in git, parsed once at the
application boundary into immutable typed objects.

**Alternatives rejected.** Hard-coded in Python — process changes become code
changes. A database-backed admin UI — better for a production deployment, and it
loses the reviewable git history that an IATF audit actually wants. Recorded as
a candidate for a future superseding decision.

**Consequences.** Positive: a quality engineer can read the configuration and
predict the system's behaviour without reading Python; every change carries an
author, date, reviewer, and reason. Negative: schema validation must be strict
and helpful, since configuration errors move from compile time to load time.
An unknown key is therefore an error, not a warning.

---

<a id="adr-0010"></a>
## ADR-0010 — Synthetic data with injected faults as the primary dataset

**Status:** Accepted · 2026-08-03

**Context.** Real wafer measurement data is customer-confidential and
unobtainable. That constraint is fixed.

**Decision.** All data is generated by `scripts/simulation/`, with a nested,
physically motivated variance structure and deliberately injected faults
carrying ground-truth manifests.

**Alternatives rejected.** Public semiconductor datasets — scarce, small, and
without ground truth on process state. Simple random generation — would make
detection trivial and every benchmark meaningless.

**Consequences.** Positive, and larger than it first appears: because faults
have known type, magnitude, and onset, the detection engine can be *scored* on
sensitivity, latency, localisation, and false-alarm rate. A real-data project
could not make that claim, since real data has no ground truth on process
state. Negative: the generator's realism becomes a project risk in its own
right (R-30), and building it credibly is a Large phase rather than a
convenience script.

---

<a id="adr-0011"></a>
## ADR-0011 — Audit trail separate from operational logging

**Status:** Accepted · 2026-08-03

**Context.** Two obligations both called "logging". Operational logs help an
engineer debug, are verbose, and are rotated aggressively. Audit records prove
what the system did and who instructed it; they are evidence, append-only, and
their deletion is an audit finding under IATF 16949.

**Decision.** Separate sinks, separate retention, separate directories
(`logs/app/` versus `logs/audit/`), and separate APIs. Audit events are
explicit calls, never a side effect of a log statement.

**Alternatives rejected.** One log stream with a severity or category field —
simpler, and it means a retention policy tuned for debug noise silently governs
compliance evidence.

**Consequences.** Positive: retention and integrity requirements can be set
correctly for each; the audit trail is queryable as a first-class dataset.
Negative: developers must consciously choose which to write, which is precisely
the point.

---

<a id="adr-0012"></a>
## ADR-0012 — Arrays in the analytics layer, DataFrames at the boundaries

**Status:** Accepted · 2026-08-03

**Context.** pandas is the default currency of Python data work, but a
DataFrame carries schema assumptions, index semantics, and a large dependency
into every function that accepts one.

**Decision.** `analytics/` accepts and returns NumPy arrays and domain value
objects. pandas appears only in `pipelines/` and `infrastructure/`.

**Alternatives rejected.** DataFrames throughout — convenient, and it couples
the statistical core to a heavy dependency with evolving semantics. Polars
throughout — better engineering in several respects, but the benefit accrues in
pipelines while the ecosystem cost is immediate.

**Consequences.** Positive: the statistical core is trivially testable with
plain arrays; a future migration from pandas to Polars touches no statistical
code; function signatures state exactly what they need. Negative: conversion at
the boundary, and slightly more verbose call sites in pipelines.

---

<a id="adr-0013"></a>
## ADR-0013 — Modular monolith, not microservices

**Status:** Accepted · 2026-08-03

**Context.** The system has clearly separable components — ingestion,
analytics, API, dashboard, reporting.

**Decision.** One deployable application with strict internal module
boundaries.

**Alternatives rejected.** Microservices — network boundaries between
components that share a transaction and a release cycle add failure modes,
latency, and operational burden while buying nothing at this scale.

**Consequences.** Positive: simple deployment into a network-restricted fab
environment; no distributed-transaction problems; boundaries are still enforced,
just at module rather than network level. Negative: components scale together.
Acceptable, since the workload is batch and the bottleneck is computation
rather than request concurrency.

---

<a id="adr-0014"></a>
## ADR-0014 — On-premises deployment assumption

**Status:** Accepted · 2026-08-03

**Context.** Semiconductor fabs do not send process data to public cloud. The
data is customer-confidential and often contractually prohibited from leaving
the site.

**Decision.** The architecture assumes an on-premises, network-restricted
deployment with **no runtime dependency on any external service**. No managed
databases, no cloud object storage, no third-party APIs in the request path.

**Alternatives rejected.** Cloud-native — operationally easier and disqualified
by the constraint. Hybrid — the complexity of both with the benefits of
neither.

**Consequences.** Positive: the design matches how the target environment
actually works, which is itself a signal of domain understanding; deployment is
simple and self-contained; no data-residency question arises. Negative: no
managed-service conveniences — backups, scaling, and monitoring are all local
responsibilities and appear explicitly in
[DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md).

---

<a id="adr-0015"></a>
## ADR-0015 — Documentation before implementation

**Status:** Accepted · 2026-08-03

**Context.** Documentation written after the code describes what was built.
Documentation written before it decides what to build — and, for an
AI-assisted project, becomes the specification the agent works from.

**Decision.** Phases 1 and 2 produce structure and documentation with no
application logic. Architecture, standards, domain vocabulary, and data model
are settled before the first line of implementation.

*Extended 2026-08-04:* Phases 3 (product requirements), 4 (Cursor rules), and 5
(module design) were inserted under the same principle and likewise produce no
application logic.

**Alternatives rejected.** Document as you go — realistic for most projects,
and it produces a vocabulary that emerges inconsistently, which is exactly the
defect source [GLOSSARY.md](GLOSSARY.md) exists to prevent. Document
afterwards — never actually happens.

**Consequences.** Positive: the agent has an authoritative specification rather
than an inference target; the vocabulary is consistent from the first commit;
architectural decisions are made deliberately rather than accreted. Negative:
significant effort before anything runs, and a real risk of documentation
drifting from implementation once code begins (R-12) — which is why
documentation updates are required in the same pull request as the change.

---

<a id="adr-0016"></a>
## ADR-0016 — Python 3.13 pinned exactly, single supported version

**Status:** Accepted · 2026-08-04

**Context.** The interpreter version had been left provisional (3.13 with a
3.12/3.13 CI matrix) pending confirmation. Two questions needed settling: which
version, and whether to support a range.

Python 3.14 was available and is the newer release. Python 3.13 has a longer
validation history across NumPy, SciPy, statsmodels, pandas, and PyArrow, and
the C-extension ecosystem is still absorbing the free-threading work introduced
around 3.14. For a platform whose entire value rests on numerical
trustworthiness, the maturity of the numerical extension modules is a more
relevant criterion than access to new language features — none of which this
codebase needs.

The range question is separate and is usually answered by reflex. Supporting
`>=3.12` is the habit of library authors, and this is not a library. It is an
application deployed as a container image with the interpreter baked in.

**Decision.** Python 3.13, pinned exactly:
`requires-python = ">=3.13,<3.14"`. CI runs 3.13 only. `uv` manages and pins
the toolchain, so the interpreter installed on any given machine is irrelevant.

Adoption of 3.14 is treated as a **scheduled revalidation exercise** with its
own decision record — running the full statistical validation suite on the new
interpreter and comparing against reference values — not as a routine
dependency bump.

**Alternatives rejected.**

*Python 3.14* — newer, and it trades validated numerical maturity for language
features the project does not use. Wrong trade for this domain.

*A supported range (`>=3.12`)* — the library-author reflex. It doubles CI
time to produce signal about a configuration that is never deployed, and it
permits a defect that reproduces on 3.12 but not 3.13, or the reverse. Where
reproducibility is the basis of a defensible analysis, "it works on several
versions" is weaker than "it works on exactly the one we ship."

*Tracking the system interpreter* — the local machine runs 3.14.3, which is
precisely why this must not be inherited from the environment.

**Consequences.**

Positive: the deployed artefact runs the exact interpreter CI validated; the
statistical validation suite certifies one configuration rather than a matrix;
CI is faster; and the upgrade path is an explicit, recorded revalidation, which
is the posture a quality organisation expects for anything that can move a
number.

Negative: the project cannot be run on 3.12 or 3.14 without an explicit
decision, which is mildly inconvenient for casual experimentation. Python 3.13
also reaches the end of full bugfix maintenance earlier than 3.14 will, so a
revalidation becomes necessary rather than optional at some point — a known,
scheduled cost rather than a surprise.

---

<a id="adr-0017"></a>
## ADR-0017 — Three-layer reference hierarchy for validation and terminology

**Status:** Accepted · 2026-08-04 · *Narrows [ADR-0004](#adr-0004)*

**Context.** [ADR-0004](#adr-0004) established that expected values in
`tests/statistical/` must come from external references, and listed
NIST/SEMATECH, Montgomery, and the AIAG manuals as candidates. Whether AIAG
should be a *numerical test dependency* was left open as Q3.

Two problems with using AIAG that way. The SPC (2nd ed.) and MSA (4th ed.)
manuals are **copyrighted commercial publications**, so reproducing their
worked-example data and expected values in a public repository carries a
licensing exposure that a portfolio project should not take on. Separately, it
is not established that their examples tabulate intermediate and final values
to the precision an automated assertion needs — an expected value a reader
cannot look up is not a citation, it is a claim.

The underlying insight is that these sources were being asked to serve three
different purposes that had been collapsed into one list. Mathematical
verification, industrial vocabulary, and semiconductor interface conventions
are separate needs, and the right authority differs for each.

**Decision.** A three-layer reference hierarchy, with each layer serving a
distinct purpose and no layer used outside it.

| Layer | Purpose | Authority | Used for |
|---|---|---|---|
| **1. Mathematical correctness** | Verifiable numerical truth | NIST/SEMATECH e-Handbook; Montgomery, *Introduction to Statistical Quality Control*, 8th ed. | Every expected value in `tests/statistical/`; every formula and constant citation |
| **2. Industrial quality alignment** | Vocabulary, methodology, acceptance conventions | AIAG SPC (2nd ed.), MSA (4th ed.); IATF 16949; VDA | Terminology, %GRR and NDC acceptance bands, control plan and reaction plan structure, documentation framing |
| **3. Semiconductor relevance** | Domain vocabulary, equipment model, data conventions | SEMI standards — E10 (RAM / equipment state), E79 (productivity, OEE), E90 (substrate tracking), E120/E125 (equipment model), E142 (substrate mapping), E148 (time synchronisation), E5/E30/E37 (SECS/GEM), E132/E134/E164 (EDA) | Domain model structure, equipment state semantics, timestamp requirements, wafer map representation, future adapter contracts |

**AIAG and SEMI are never numerical test dependencies.** No expected value in
an automated test cites them. Layer 1 alone carries that role, because both of
its sources are publicly accessible and independently checkable by any
reviewer.

**Alternatives rejected.**

*Add AIAG worked examples as test fixtures* — recognisable to an IATF auditor,
and it introduces a licensing exposure and depends on precision that has not
been confirmed. The recognition benefit is obtainable through Layer 2 without
reproducing any copyrighted data.

*NIST/SEMATECH only* — free and thorough, and thinner on the subgroup-size
boundary cases and chart variants Montgomery tabulates. Two independent
mathematical sources are also mutually checking, which one is not.

*Derive all expected values by hand* — hand computation remains a supplementary
method for cases no publication tabulates ([TESTING_STRATEGY.md](TESTING_STRATEGY.md)
§3.2), but as the primary authority it would mean the tests verify the author's
arithmetic rather than an independent source. That is exactly the circularity
ADR-0004 exists to prevent.

**Consequences.**

Positive: every numerical assertion cites a source a reviewer can obtain
without purchase, which materially strengthens the correctness claim — a
verification anyone can reproduce is worth more than one behind a paywall. No
licensing exposure. And separating the layers clarifies what was previously
muddled: AIAG's real value here is methodological alignment and acceptance
convention, not arithmetic, and it is now used for exactly that.

Negative: no AIAG-sourced numerical case, so an auditor cannot be shown a test
asserting against a manual they recognise. Mitigated by Layer 2 — the
methodology, terminology, and acceptance bands still align with AIAG, and
[QUALITY_ASSURANCE_PLAN.md](QUALITY_ASSURANCE_PLAN.md) §2 maps the platform to
those requirements explicitly.

**Note on Layer 3.** SEMI standards are likewise controlled publications and
carry the same restriction: conceptual alignment only, never reproduced, never
a numerical dependency, and no conformance claimed. The alignment is
nonetheless load-bearing rather than decorative — E120/E125 shape the tool →
chamber hierarchy in the domain model, E10 supplies the equipment state
semantics that make a step shift interpretable, and E148 underwrites the
timezone-aware timestamp rule. Recorded in full in
[domain/SEMI_STANDARDS_ALIGNMENT.md](domain/SEMI_STANDARDS_ALIGNMENT.md).

---

<a id="adr-0018"></a>
## ADR-0018 — Interactive Plotly wafer maps; static images for export only

**Status:** Accepted · 2026-08-04 · *Resolves Q4*

**Context.** A wafer map plots measurements at their true site coordinates. It
is the screen where spatial signatures become visible — centre-to-edge, edge
ring, left-right asymmetry, slot-correlated patterns — and those are invisible
in a time series while frequently carrying the root cause. Two rendering
approaches were open: an interactive figure, or a precomputed static image.

The deciding requirement is **drill-down**. A quality engineer looking at an
anomalous site needs to reach its lot ID, wafer ID, slot, site coordinates,
measured value, and deviation from target — without leaving the screen. A
static image can display a pattern but cannot answer "which wafer, and what was
the value?", which is the question that follows within seconds of noticing the
pattern.

**Decision.** Interactive Plotly figures embedded in Streamlit are the primary
wafer map visualisation. Static images are supported only as export and
reporting artefacts.

### Rendering pipeline, mapped onto the architecture

The pipeline is constrained by [ADR-0002](#adr-0002): no statistical
computation in `dashboard/`.

| Stage | Location | Responsibility |
|---|---|---|
| Measurement retrieval | `infrastructure/` | Repository query, filtered by lot / wafer / parameter / window |
| Spatial signature detection | `analytics/spatial/` | Radial, edge, asymmetry classification — pure functions over arrays |
| View assembly | `application/` — `GetWaferMap` use case | Attach site coordinates, compute deviation from target, apply the point budget, return a `WaferMapView` value object |
| Figure construction | `dashboard/components/wafer_map.py` | `WaferMapView` → Plotly figure. Pure rendering, zero computation |
| Presentation and caching | `dashboard/state/` | Streamlit caching, filter state |
| Static export | `reports/` | Deterministic Matplotlib render of the same `WaferMapView` |

`WaferMapView` is the seam that makes this work. Both the interactive figure and
the static export consume the identical value object, so a wafer map in a PDF
report and one on screen cannot disagree — they are two renderings of one
computation, not two computations.

### Implementation requirements

- Individual site markers at true coordinates (mm from wafer centre)
- Hover metadata: lot ID, wafer ID, slot, site ID, coordinates, value, unit,
  deviation from target
- Wafer boundary, notch or flat orientation, and exclusion zone drawn explicitly
- Defect and deviation heatmaps, including binned/contour representation
- Filtering by lot, wafer, tool, chamber, parameter, and time window
- Streamlit caching per the invalidation rule below
- A point budget preventing production-scale rendering in one figure

### Two failure modes designed out

**Per-wafer colour autoscaling.** If each wafer's colour scale is fitted to its
own range, every wafer looks alike and the differences between them — the entire
point of comparing wafers — disappear. A wafer varying by 0.2 nm and one
varying by 20 nm render identically. **Colour scale limits are fixed across any
comparison set** and displayed numerically on the legend. Per-wafer autoscaling
is available only as an explicit, labelled user action.

**Perceptually non-uniform colour maps.** Rainbow and jet scales introduce
sharp perceived boundaries where the data is smooth. On a wafer map this
manufactures an apparent edge ring or radial band that does not exist —
fabricating exactly the signature the screen is meant to detect, which is a
correctness defect rather than an aesthetic one. **Perceptually uniform,
colour-vision-safe scales only:** sequential (viridis, cividis) for raw values,
diverging centred on target for deviation.

### Scale guardrail

A single wafer is at most 49 sites and a lot at most ~1 200 points, both
trivial. The risk is an unfiltered query spanning months.

- Hard cap of ~5 000 individually rendered site markers per figure.
- Above the cap, the view degrades to an aggregated representation — wafer-level
  means, or binned contours — **and states on screen that it has aggregated.**
  Consistent with [CODING_STANDARDS.md](CODING_STANDARDS.md) §1.4: the interface
  never silently substitutes something other than what was asked for.
- A wafer map query without a lot, wafer, or time filter is rejected rather than
  attempted.

### Cache invalidation

Streamlit caching is required for responsiveness and is a correctness hazard.
**Cache keys include the data revision and the configuration revision**, so
reprocessed data or a recalculated baseline invalidates automatically. A screen
serving a cached map built from superseded data is a correctness bug, not a
performance detail.

**Alternatives rejected.**

*Precomputed static images* — cheap, fast, and they cannot answer the question
that immediately follows noticing a pattern. Retained for export, where
determinism matters more than interaction.

*A dedicated JavaScript visualisation component* — more control over rendering
at large point counts, at a build and maintenance cost unjustifiable for this
audience and team size, and inconsistent with [ADR-0006](#adr-0006).

*Matplotlib embedded in Streamlit* — static in practice; keeps the Matplotlib
dependency without gaining interaction.

**Consequences.**

Positive: the drill-down requirement is met; one `WaferMapView` feeds both
screen and report, so they cannot diverge; the two visualisation failure modes
above are settled by decision rather than discovered during review.

Negative: Plotly performance at high point counts is asserted rather than
measured, and this is the residual part of R-42. The point budget bounds the
exposure, and because `dashboard/` holds no computation, replacing the renderer
touches presentation only. A `tests/performance/` case will pin the budget once
the dashboard phase begins.

---

<a id="adr-0019"></a>
## ADR-0019 — Modules are capability slices, not packages

**Status:** Accepted · 2026-08-04

**Context.** Phase 5 fixed the platform's functional decomposition at ten named
modules: ingestion, preprocessing, SPC engine, capability, KPI and trend,
anomaly detection, root cause, change control simulation, dashboard and
reporting, and utilities and configuration.

That decomposition has to coexist with the hexagonal arrangement in
[ADR-0002](#adr-0002), and the two are not obviously compatible. The modules are
organised by *what capability is delivered*; the layers are organised by *what
may depend on what*. A decision was needed about which one the package structure
expresses, because both cannot own it.

**Decision.** A module is a **capability slice**, not a Python package. Each
module owns one capability end to end and distributes its parts across the
existing layers according to what each part does: domain types in `domain/`,
computation in `analytics/`, orchestration and policy in `application/`, zone
movement in `pipelines/`, I/O in `infrastructure/`, rendering in `dashboard/`.

Modules decompose responsibility; layers continue to decompose dependency. The
module dependency graph in [MODULE_DESIGN.md](MODULE_DESIGN.md) §3 is acyclic
and is enforced alongside the layering rule by `import-linter`, so both
decompositions are mechanical rather than aspirational.

**Alternatives rejected.**

*Ten top-level packages, one per module.* The obvious reading of the
requirement, and it breaks the property the architecture exists to protect. A
package named for a capability contains that capability's statistics,
orchestration, and I/O in one import unit, which makes the inward-only rule
unenforceable and — decisively — makes `analytics/` impure. Verifying a Cpk
calculation would then require a database fixture, and the statistical test tier
in [ADR-0004](#adr-0004) becomes impossible. The cost is not stylistic.

*Replacing hexagonal with vertical slice architecture.* Coherent in general and
wrong here for two specific reasons. The statistical core is shared by most of
the ten modules, so a slice-per-capability arrangement either duplicates it —
unacceptable when correctness is the product — or reintroduces a shared kernel,
which is the layer model under a different name. And the port boundary that lets
a synthetic Parquet source be swapped for a fab MES is the second thing the
architecture is for; slices would scatter that seam across ten places.

*Treating the ten modules as documentation labels with no structural meaning.*
Cheap and honest about the mismatch, but it leaves "where does this code go?"
unanswered, which is the question the structure exists to answer for both a new
contributor and the agent. A decomposition nothing enforces drifts within weeks.

**Consequences.**

Positive: every functional requirement area has an owning module and no area is
unowned; the module graph is enforceable as `import-linter` contracts from
Phase 6, before any code exists to violate it; the agent can locate the right
file from the module specification without inferring architecture; and the
layering guarantees that make the statistical tier possible are untouched.

Negative: a module's code is not co-located, so reading "all of Module 4" means
visiting four directories rather than one. Each module specification lists the
files it owns precisely to offset that. The mapping is also a maintenance
surface — a file added without updating its module specification is documentation
drift of exactly the kind R-12 predicts, which is why the specifications name
files rather than describing them in prose.

---

<a id="adr-0020"></a>
## ADR-0020 — One gate script for local and CI

**Status:** Accepted · 2026-08-04

**Context.** Phase 6 introduced the quality gates that every later phase must
pass through. `make check`, the pre-commit hooks, and GitHub Actions each need
to run those gates. If each caller holds its own copy of the commands — a
Makefile recipe here, a workflow step there, a hook entry elsewhere — a green
local run quietly stops meaning what a green pipeline means, and the
discrepancy is discovered only when a merge fails or, worse, when it does not.

**Decision.** Every quality gate is defined once, in
`scripts/ci/gate.sh`, and named. `make`, pre-commit, and GitHub Actions invoke
that script by gate name. Adding a gate or changing a gate's command is a
one-file change; a caller that does not go through the script is a defect.

**Alternatives rejected.**

*Duplicated commands in Makefile and workflow.* The default, and the failure
mode this decision exists to prevent. Local and CI diverge within weeks.

*A Python orchestration package.* More expressive, and more to maintain before
there is any application logic. A shell script with named gates is enough for
the gate set in [QUALITY_ASSURANCE_PLAN.md](QUALITY_ASSURANCE_PLAN.md) §3, and
it runs identically under `make` and Actions.

*Task runners that embed the commands (Just, Invoke).* Useful for developer
ergonomics, but they would become a second definition unless they also call
`gate.sh`. Adding a layer that still needs the script buys nothing.

**Consequences.**

Positive: `make check` and CI cannot disagree about what was checked; a gate
change is reviewable in one place; empty test tiers report as EMPTY rather than
passing silently, which keeps the gate honest until each tier is populated.

Negative: the script is a shell surface that every contributor and the agent
must treat as authoritative. Gate names are part of the public contract between
the Makefile and the workflow, and renaming one without updating both callers
breaks the run — which is still better than silent divergence.

---

**Related:** [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) ·
[MODULE_DESIGN.md](MODULE_DESIGN.md) ·
[TECH_STACK.md](TECH_STACK.md) ·
[RISK_REGISTER.md](RISK_REGISTER.md) ·
[architecture/repository-structure.md](architecture/repository-structure.md)
