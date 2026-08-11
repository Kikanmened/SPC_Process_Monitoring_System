# Project Progress

**Document owner:** Project lead
**Status:** Living document — updated at the close of every working session
**Last updated:** 2026-08-10

The current state of the project in one place. This is the document to read
first when resuming work after a break, and the one the AI agent should consult
to establish where things stand rather than inferring it from the file tree.

For the plan see [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md); for the
release history see [CHANGELOG.md](../CHANGELOG.md).

---

## 1. Status at a glance

| | |
|---|---|
| **Current phase** | Phase 15 — Advanced analytics (stretch, gated) |
| **Phases complete** | 14 of 15 |
| **Application code** | Domain through pipelines, use cases, API/CLI, dashboard, reports, deploy |
| **Repository** | Initialised; see git remotes for hosting |
| **Last milestone** | M14 — deployable stack (2026-08-10) |
| **Next milestone** | M15 — advanced analytics (stretch only) |

```
Phase  1 ████████████ Structure              complete
Phase  2 ████████████ Documentation          complete
Phase  3 ████████████ Product requirements   complete
Phase  4 ████████████ Cursor rules           complete
Phase  5 ████████████ Module design          complete
Phase  6 ████████████ Toolchain + CI         complete
Phase  7 ████████████ Domain model           complete
Phase  8 ████████████ Data generator         complete
Phase  9 ████████████ Analytics engine       complete
Phase 10 ████████████ Pipelines + storage    complete
Phase 11 ████████████ Application + API      complete
Phase 12 ████████████ Dashboard              complete
Phase 13 ████████████ Reporting + audit      complete
Phase 14 ████████████ Deployment             complete
Phase 15 ░░░░░░░░░░░░ Advanced analytics (stretch)
```

## 2. Completed work

### Phase 1 — Project structure · 2026-08-03

96-directory production structure with a documented rationale for every
top-level folder.

- src layout under `src/spc_platform/` with hexagonal subdivision
- Six-tier test structure, statistical validation separated as its own tier
- Eight data zones with a one-directional flow contract
- Scoped ignore policy: source committed, generated artefacts excluded,
  directory skeleton preserved
- READMEs in all thirteen top-level directories
- `docs/architecture/repository-structure.md` as the canonical rationale
- Git repository initialised on `main`

**Verified:** artefacts in `data/raw/`, `logs/app/`, `models/artifacts/`, and
`reports/generated/` confirmed ignored while the skeleton and documentation
remain tracked.

### Phase 2 — Project documentation · 2026-08-03

Fifteen documents establishing context, architecture, standards, and plan
before any implementation.

- Domain framing and vocabulary: `PROJECT_CONTEXT`, `GLOSSARY`
- Technical design: `SYSTEM_ARCHITECTURE`, `TECH_STACK`, `DECISION_LOG`
  (15 ADRs)
- Engineering discipline: `CODING_STANDARDS`, `TESTING_STRATEGY`
- Data and quality system: `DATASET_GUIDE`, `QUALITY_ASSURANCE_PLAN`
- Planning and tracking: `DEVELOPMENT_ROADMAP`, `RISK_REGISTER`,
  `PROJECT_PROGRESS`, `CHANGELOG`
- Operations: `DEPLOYMENT_PLAN`
- Entry point: root `README`

### Phase 3 — Product requirements · 2026-08-04

[PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) — the enterprise PRD, and
the requirement baseline the remaining phases deliver against.

- Six business objectives, each with a measurable success criterion
- Product metrics separated from engineering metrics, so "the build is green"
  is never mistaken for "the platform detects excursions"
- Five personas, with the shift lead's question prioritised because it is asked
  most often and under the most pressure
- 74 functional requirements across eleven areas, each with an identifier and
  a MoSCoW priority
- Non-functional requirements in eight categories, with numeric budgets rather
  than adjectives
- Three Phase 2 open questions resolved as ADR-0016 through ADR-0018
- Four user story epics; Given/When/Then acceptance criteria for the
  highest-risk behaviours, including the refusals
- Fourteen milestones mapped to phases, and a four-level definition of done

**Design note:** the acceptance criteria deliberately specify what the system
must **refuse** — no chart without a qualified baseline, no capability index on
an unstable process — because those refusals are the requirements most likely
to be quietly implemented as a helpful default (R-21).

### Phase 4 — Cursor rules · 2026-08-04

One lightweight global core plus six professional path-scoped rules in
`.cursor/rules/`, each with one responsibility:

- Project core — source-of-truth routing, uncertainty handling, scope
  discipline, and universal safety constraints
- Product management — requirement traceability, stories, acceptance criteria,
  prioritization, and product change control
- Semiconductor quality engineering — fab vocabulary, SPC, capability, MSA,
  change control, and evidence-based root-cause practice
- Senior Python architecture — dependency direction, SOLID, modular design,
  reuse, patterns, and performance
- Testing engineering — pytest strategy, tier boundaries, regression evidence,
  mocking, coverage, and CI behavior
- GitHub maintenance — branch and PR policy, Conventional Commits, issue
  quality, Actions security, and repository hygiene
- Documentation writing — Markdown, APIs, architecture, ADRs, READMEs, and
  verifiable technical claims

**Verified:** all seven rules use valid `.mdc` frontmatter and stay under 50
lines. `project-core.mdc` is the only `alwaysApply: true` rule; all six
specialists declare narrow path scopes and set `alwaysApply: false`. The core
routes to authoritative project documents rather than duplicating them.

### Phase 5 — Module design · 2026-08-04

[MODULE_DESIGN.md](MODULE_DESIGN.md) plus ten specifications in
[modules/](modules/), decomposing the platform into ten modules and mapping
them onto the layers they are built inside.

- Modules defined as **capability slices, not packages** — ten top-level
  packages would put computation, orchestration, and I/O in one import unit and
  break the inward-only rule
- Ten specifications, each stating purpose, responsibilities, public interfaces,
  dependencies, inputs, outputs, files to create, testing requirements,
  documentation required, and extension points
- An acyclic module dependency graph, intended to be encoded as `import-linter`
  contracts in Phase 6
- A requirement coverage map: every functional requirement area in the PRD has
  an owning module
- [ADR-0019](DECISION_LOG.md#adr-0019) recording the capability-slice decision
  and the alternatives rejected

**Design note:** four capabilities in the requested decomposition exceed the
requirement baseline, and they are recorded as **proposed** identifiers rather
than assumed — FR-K01 – FR-K06 (KPI), FR-AD01 – FR-AD04 (detector contract and
scoring), FR-RC01 – FR-RC04 (evidence assembly), FR-CC01 – FR-CC06 (change
control simulation). None is in the PRD, and nothing may be built against them
until it is amended. Two boundaries were held rather than proposed away:
Module 7 assembles root-cause *evidence* and never asserts a cause, and
Module 6 delivers the detector contract and scoring harness while model-based
detection stays gated behind Phase 15.

### Phase 6 — Toolchain and CI foundation · 2026-08-04

The mechanical quality gates, in place before the first line of application
code so that nothing is ever written outside them.

- `pyproject.toml` (PEP 621, src layout, `requires-python = ">=3.13,<3.14"`),
  the `uv` environment, and a committed `uv.lock`
- Ruff, `mypy --strict`, and pytest with a marker per test tier — the marker
  applied from the directory in `tests/conftest.py`, and a test outside a tier
  directory refused at collection
- Ten `import-linter` contracts: the inward-only layer rule, domain
  self-containment, analytics purity (including a ban on `pandas` and on
  reading a clock), the port rule for the application layer, presentation as a
  leaf, and the module dependency graph from
  [MODULE_DESIGN.md](MODULE_DESIGN.md) §3
- `pre-commit` with `nbstripout`, `gitleaks`, and a Conventional Commits
  `commit-msg` hook enforcing the `stat:` marker
- `Makefile` exposing every gate, and GitHub Actions running the same gates
  through the same script
- Issue templates, pull request template, and `CODEOWNERS`

**Design note:** every gate has exactly one definition, in
`scripts/ci/gate.sh`, and `make`, pre-commit, and GitHub Actions all call it by
gate name ([ADR-0020](DECISION_LOG.md#adr-0020)). The alternative — each caller
holding its own copy of the command — is how a green local run quietly stops
meaning what a green pipeline means.

**Verified by deliberate violation, not by assertion.** A `domain/` module
importing `analytics/` broke two contracts; a `pandas` import in `analytics/`
broke the purity contract; a planted credential was caught by `gitleaks`; a
broken link and a broken anchor were caught by the documentation check; a
non-conforming commit subject was rejected. Each was then removed and the gate
returned to green.

**Known partial:** the module dependency graph is encoded over the fourteen
`analytics/` packages named in the module specifications, every layer marked
optional so the contract tightens as each package lands in Phases 9–13. The
module boundaries that live in `application/` are covered only by the
layer-level contracts until those packages exist.

### Phase 7 — Domain model and configuration · 2026-08-04

The vocabulary of the fab as types, and the typed configuration system that
every later module will parse once at the boundary.

- Domain entities and value objects per
  [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §3.1: material hierarchy,
  equipment, parameter, measurement, baseline, subgroup, violation, disposition,
  chart/rule specs
- **`SpecificationLimit` and `ControlLimit` as structurally distinct,
  non-convertible types** — no shared constructor parameters, no conversion
  methods, and a type-level unit test that fails if either is introduced
  (FR-C06, ADR-0003)
- `Measurement` carrying value, unit, timezone-aware timestamp, chamber,
  metrology tool, and data revision (FR-D01)
- Layered typed settings (`configs/base/` + environment overlay) with unknown
  keys raising (FR-CF02); effective configuration revision hash (FR-RP02)
- Unit registry with declared conversions only (FR-D08)
- Committed reference data under `data/reference/` for a minimal gate-module
  slice (parameters, specs, tools, steps, control plans)
- Pandera schemas for raw / interim / processed zone boundaries
  (`src/spc_platform/pipelines/schemas/`)
- ADR-0020 recorded (single gate script) — it was referenced by Phase 6 but
  had been missing from the decision log

**Exit criteria met:** every domain invariant has a failing-construction test;
ControlLimit cannot be built from a specification payload (and the reverse);
`domain/` imports nothing from this repository (`import-linter` green); unknown
configuration keys raise. `make check` passes with 64 unit tests.

### Phase 8 — Synthetic fab data generator · 2026-08-04

The measurement instrument for every detection claim the platform will make.

- `data/reference/` expanded to a full fab: 12 process steps, 26 parameters, 27
  process tools across 80 chambers, 15 gauges, 3 devices on 2 nodes, 45
  specification limits, and 6 control plans charting 44 characteristics
- `src/spc_platform/simulation/` — configuration models, fab topology, nested
  variance, wafer sampling plans and spatial signatures, fault injection,
  ground-truth manifests, deterministic writers, and independent statistical
  validators
- Eight injected faults with a manifest recording kind, scope, onset lot and
  instant, and magnitude in both sigma and the parameter's own unit
- `spc_platform/infrastructure/vcs.py` reading the code revision, marking it
  `-dirty` when the working tree is modified
- Thin operator scripts and `make dataset`, `dataset-check`, `dataset-bench`

**Design note:** the generator is an instrument, not a dependency
([ADR-0021](DECISION_LOG.md#adr-0021)). Two `import-linter` contracts stop it
reaching `analytics/` and stop the platform reaching it. Without the first, the
benchmark would confirm itself — the same error on both sides would cancel and
every score would look excellent. That is why `simulation/validators.py`
deliberately re-implements statistics `analytics/` will also compute.

**Verified against ground truth, not against itself.** 153 statistical checks
pass on the default 500-lot dataset. Each injected fault is separately shown
present in the data with its declared magnitude, onset, and scope: the cyclic
fault's period is recovered by a least-squares sinusoid fit over the lot numbers
the points actually carry, the tool excursion is shown to move its own tool and
not the fleet, and the metrology drift is shown to follow its gauge across
unrelated parameters. A dataset regenerates with an identical content digest,
and the digest survives a round trip through both Parquet and CSV.

**Four defects the tests caught, each of which would have corrupted the
benchmark silently:**

- The content digest hashed string columns by *memory address*, so two
  identical frames digested differently and the reproduction guarantee was
  vacuous.
- Outlier injection applied each source once per distinct chamber in a block,
  with the same random key each time — multiplying the magnitude by the chamber
  count and over-counting in the manifest.
- Remeasurement re-drew Poisson counts with Gaussian gauge noise, producing
  20.4 defects on remeasured wafers only.
- The benchmark script timed the generator with `tracemalloc` running, reporting
  a throughput 6.6× below the real one.

**Known limitation:** three characteristics in the default dataset are reported
as unchecked rather than passed — they carry the faults, and a faulted
characteristic has no clean quantity to compare. The report names them rather
than counting them as coverage.

**Exit criteria met:** distributions match the configured parameters within
tolerance; the spatial signature reproduces across wafers at correlation > 0.95;
variance decomposition recovers the configured components; a dataset regenerates
byte-identically. `make check` passes with 252 tests and 12 `import-linter`
contracts.

### Phase 9 — SPC analytics engine · 2026-08-05

The statistical core the rest of the platform is scored on.

- `analytics/estimators/` — control-chart constants derived from their integral
  definitions (Tippett, gamma ratios), checked against Montgomery Appendix VI;
  short-term and long-term sigma estimators that carry their method identity
- `analytics/charts/` — I-MR, X̄-R, X̄-S, EWMA, CUSUM, p/np/c/u; Phase I studies
  separate from Phase II panels with fixed limits (FR-C03)
- `analytics/rules/` — Western Electric and Nelson from shared vectorised
  primitives; measured ARL₀ within ±15% of theory
- `analytics/capability/` and `analytics/msa/` — Cp/Cpk/Pp/Ppk/Cpm with named
  estimators; gauge R&R by ANOVA, bias, linearity, stability
- `analytics/variance/` — nested variance decomposition (FR-S07)
- `analytics/spatial/` — radial / edge / asymmetric / **none**, with none the
  default; geometric predictors that do not share code with the generator
  (ADR-0021, FR-S02)
- `analytics/scoring/` — detection scorecard against known onsets (test harness;
  FR-AD01 – FR-AD04 remain proposed and unimplemented)
- `configs/spc/` chart defaults and named rule sets;
  `docs/validation/detection-performance.md` publishes the measured figures

**Verified against references and ground truth, not against itself.** Detection
rate 100% at 1.5σ and at 3σ across 200 seeded trials; localisation 99% within
±3 points at 3σ; Shewhart ARL₀ ≈ 370 and Western Electric ARL₀ ≈ 91.75 within
tolerance; 1 000 points with Nelson's full set under the 50 ms budget.

### Phase 10 — Data pipelines and persistence · 2026-08-06

Raw exports become analysis-ready series with hard-stop validation and one
repository port for Fake, DuckDB, and PostgreSQL (ADR-0008).

- `pipelines/ingest/` — Pandera raw validation, measurement-key uniqueness,
  quarantine on failure, content-addressed `data_revision`, run records
- `pipelines/transform/` — context check, re-measurement supersession, unit
  normalisation, atomic processed publish; `build_subgroups` at the series
  boundary (site grain preserved in the processed zone)
- `infrastructure/readers/` and `infrastructure/repositories/` — file source;
  Fake / DuckDB / PostgreSQL measurement and baseline stores
- Alembic initial schema under `migrations/`; shared DDL for DuckDB
- `scripts/pipelines/run_pipeline.py` — local composition root

**Verified:** quarantine leaves interim untouched; processed rows carry
`data_revision`; Fake and DuckDB pass the contract suite; PostgreSQL and
Alembic round-trip run when `SPC_TEST_DATABASE_URL` is set.

**Exit criteria met.** Application use cases and detector registries are
deliberately deferred (Phase 11; proposed FR-AD01 – FR-AD04).

### Phase 11 — Application layer, API, and CLI · 2026-08-06

Seven use cases share one code path for FastAPI and the Typer CLI. Capability
reports refuse out-of-control windows (FR-P04). Append-only audit covers the
QA §2.2 events these use cases emit.

- Ports: `AuditSink`, `Authorisation`, violation / disposition / specification
  repositories; local fake + JSONL file audit adapters
- Use cases under `application/use_cases/`; composition via
  `infrastructure/composition/`
- FastAPI under `api/` with `X-Actor-Id` (SSO deferred to Phase 14)
- Typer CLI with console script `spc`
- Contract OpenAPI validation; e2e API ≡ CLI for `evaluate_lot`

**Verified:** fake-adapter unit tests including FR-P04 refusal and audit abort;
OpenAPI contract tests; append-only file integration; e2e evaluate_lot and
capability refusal.

**Exit criteria met.** No message bus. Site SSO remains Phase 14.

### Phase 12 — Dashboard · 2026-08-07

Streamlit screens over application view models. Plotly wafer maps and Matplotlib
static export share one `WaferMapView`. Spec limits are dashed; control limits
are solid; OOC uses shape and label. Marker budget 5 000 with labelled
aggregation. Tool comparison uses Welch's t-test (FR-T01). Trends refuse
proposed Module 5 KPIs.

**Verified:** dashboard does not import analytics; dual-render test; performance
budget for wafer-map assembly; `make demo` launches the app.

**Exit criteria met.**

### Phase 13 — Reporting, excursion workflow, and audit packages · 2026-08-10

Jinja2 HTML reports with provenance headers; WeasyPrint PDF when native
libraries are available. Excursion lifecycle from detection through closure
with mandatory disposition and 8D/CAPA. Digested notifications and control-plan
OCAP on the alarm queue. Audit packages are zip archives with SHA-256 digests.

**Verified:** FR-RP03 HTML regeneration contract; provenance on every artefact
type; e2e violation → excursion summary; `make check` green at 0.13.0.

**Exit criteria met.** Containerised PDF runtime and SSO remain Phase 14.

### Phase 14 — Deployment and operations · 2026-08-10

On-prem Compose stack matching DEPLOYMENT_PLAN.md: multi-stage non-root image,
local DuckDB profile and staging Postgres overlay, scheduler jobs, health and
metrics, backup/restore drill, runbooks. SSO is trusted reverse-proxy headers
(`SPC_AUTH_MODE=proxy`), not an invented LDAP client.

- `Dockerfile`, `docker-compose.yml`, `docker-compose.staging.yml`; `make stack`
- Scheduler under `src/spc_platform/scheduler/` (ingest, evaluate, notify,
  daily-report, archive, backup) with fingerprint idempotency
- `/health`, `/ready`, `/metrics`; structlog JSON; `spc-platform health`
- Ops scripts and runbooks under `scripts/ops/` and `docs/runbooks/`

**Verified:** job double-run fingerprints (NFR-R01); backup/restore unit drill
(NFR-R03); API health/ready/metrics; `make check` green at 0.14.0.

**Exit criteria met.** Kubernetes remains deferred. Phase 15 is stretch only.

## 3. Decisions settled

Twenty-two architecture decisions are recorded in
[DECISION_LOG.md](DECISION_LOG.md). The five that most constrain everything
that follows:

1. **Specification and control limits are distinct, non-convertible types.**
   The defining error of poor SPC tooling is made structurally impossible
   rather than reviewed for.
2. **Statistical validation is a separate test tier** with expected values from
   NIST/SEMATECH and Montgomery exclusively — both publicly obtainable.
   Snapshotting current output is prohibited.
3. **SPC mathematics is implemented in-house** on NumPy/SciPy/statsmodels —
   it is the substance of the project, not a dependency.
4. **The data generator precedes the analytics engine**, so every detection
   algorithm is scored against known ground truth from its first commit.
5. **Deployment is on-premises with no external runtime dependencies**, because
   that is how fabs actually operate.

## 4. Open questions

Tracked here until they become decisions. None currently blocks Phase 15 stretch work.

| # | Question | Needed by | Notes |
|---|---|---|---|
| ~~Q1~~ | ~~Confirm the Python version pin~~ | — | **Resolved 2026-08-04.** Python 3.13, pinned exactly, single supported version. [ADR-0016](DECISION_LOG.md#adr-0016) |
| ~~Q2~~ | ~~Does the local demo profile need PostgreSQL parity, or is DuckDB alone sufficient for review?~~ | — | **Resolved 2026-08-06.** DuckDB-only for clone-and-run; the same contract suite covers Fake + DuckDB always and PostgreSQL when `SPC_TEST_DATABASE_URL` is set. |
| ~~Q3~~ | ~~Which reference datasets to standardise on for the statistical tier~~ | — | **Resolved 2026-08-04.** NIST/SEMATECH and Montgomery only for numerical expectations; AIAG for quality alignment, SEMI for domain conventions. [ADR-0017](DECISION_LOG.md#adr-0017) |
| ~~Q4~~ | ~~Wafer map rendering approach in Streamlit~~ | — | **Resolved 2026-08-04.** Interactive Plotly primary, static images for export only. [ADR-0018](DECISION_LOG.md#adr-0018) |

All questions raised during Phase 2 are now resolved. Phase 5 raised one:

| # | Question | Needed by | Notes |
|---|---|---|---|
| Q5 | Are the twenty proposed requirements from module design approved, and does the PRD get amended to include them? | Phase 15 / Modules 5–8 | FR-K01 – FR-K06, FR-AD01 – FR-AD04, FR-RC01 – FR-RC04, FR-CC01 – FR-CC06. Modules 5, 6, 7, and 8 are specified but partly unbuildable until this is settled ([MODULE_DESIGN.md](MODULE_DESIGN.md) §5) |

New questions are added here as they arise.

## 5. Active risks

Full register in [RISK_REGISTER.md](RISK_REGISTER.md). Requiring attention now:

| ID | Risk | Why it is live |
|---|---|---|
| R-20 | AI fabrication of statistical constants | The statistical tier now has hundreds of reference-backed cases and derived constants checked against Montgomery Appendix VI. The remaining gap is mechanical enforcement that every new constant carries a citation — still a review criterion. |
| R-12 | Documentation drift | Growing code against living docs. The link gate catches broken references; stale claims still need a human. Phase 9 figures in the validation scorecard were taken from the seeded tests, not invented. |
| R-04 | Rational subgrouping error | Phase 11 `evaluate_lot` charts individuals from site-grain series against the active baseline; wrong grain remains a configuration risk if a future use case aggregates without an explicit strategy. |
| R-10 | Scope expansion | Phase 15 is deliberately gated, and Phase 5 recorded twenty proposed requirements rather than absorbing them. Approving them all would expand the release scope materially (Q5). |

## 6. Next actions

Phase 15 is stretch and gated (R-10). Attempt only when Phases 1–14 remain solid
and a candidate from DEVELOPMENT_ROADMAP.md Phase 15 is explicitly chosen.

Until then: operate the stack (`make stack`), keep restore drills current, and
resolve Q5 before building proposed Modules 5–8 requirements.

## 7. Metrics

Populated as the project progresses. Zeros below are accurate, not placeholders.

| Metric | Current | Target |
|---|---|---|
| Phases complete | 14 / 15 | 15 |
| Cursor rules | 7 | 7 |
| Documentation files | 30 | — |
| Identified requirements | 74 FR + 43 NFR | Traced to tests |
| Proposed requirements awaiting approval | 20 | Approved or rejected (Q5) |
| Modules specified | 10 / 10 | 10 |
| Modules with code landed | 9 / 10 (+ Module 10 observability/proxy auth; Module 9 reports; Module 7 excursions) | 10 |
| Tests | 870+ across six tiers (Postgres cases skipped without URL) | — |
| Statistical checks on the default dataset | 153 passed, 3 characteristics unchecked | Every characteristic checked |
| Reference-validated statistical cases | Full analytics suite (constants, charts, rules, capability, MSA, ARL, detection power, spatial) | Maintained |
| Type coverage | 100% under `mypy --strict` | 100% |
| Architecture violations | 0 | 0 |
| Detection rate (shifts ≥ 1.5σ) | 100% on 200 seeded trials | ≥ 95% |
| Measured ARL₀ deviation from theory | within ±15% (WE and Shewhart) | within ±15% |

## 8. Session log

Newest first. One entry per working session, recording what changed and what
the next session should pick up.

### 2026-08-10 — Phase 14: Deployment and operations

Closed the on-prem deploy path. Compose brings up API, dashboard, and scheduler;
jobs are idempotent by fingerprint; backup/restore is tested; runbooks cover
startup, jobs, failure, and restore. Proxy SSO mode consumes
`X-Forwarded-User`.

**Verified:** NFR-R01 / NFR-R03 tests; health endpoints; `make check` at 0.14.0.

**Next:** Phase 15 only if explicitly chosen (stretch).

### 2026-08-10 — Phase 13: Reporting, excursion workflow, and audit packages

Closed report artefacts and the excursion lifecycle. Jinja2 HTML reports carry
data/code/config revisions; WeasyPrint PDF is optional when system libraries
are present. Excursions close only with disposition plus 8D/CAPA. Digests and
audit-package zips are audited.

**Verified:** regeneration contract, provenance headers, e2e excursion summary,
`make check` green at 0.13.0.

**Next:** Phase 14 — deployment and operations.

### 2026-08-07 — Phase 12: Dashboard

Closed the presentation layer for operator screens. Streamlit multipage app
calls application view builders only; import-linter denies `dashboard` →
`analytics`. Wafer maps fix colour limits across comparison sets, use
viridis/cividis/diverging scales, and aggregate above 5 000 markers with an
on-screen statement. Plotly and Matplotlib share one `WaferMapView`.

**Verified:** dual-render unit test, no-analytics import test, wafer-map
performance budget, `make check` green at 0.12.0. Launch with `make demo`.

**Next:** Phase 13 — reporting, excursion workflow, and audit packages.

### 2026-08-06 — Phase 11: Application layer, API, and CLI

Closed the application boundary. Seven use cases call analytics through
ports; FastAPI and Typer share that path. Capability refuses unstable
windows (FR-P04) with an audited `report_refused` event. Audit is append-only
(fake + JSONL). Actor identity is `X-Actor-Id` / `--actor` only — SSO waits
for Phase 14. No message queue.

**Verified:** unit, contract, integration, and e2e coverage for use cases,
OpenAPI shapes, audit append-only behaviour, and API ≡ CLI evaluate_lot.
`make check` green after docs and version bump to 0.11.0.

**Next:** Phase 12 — Streamlit dashboard over these use cases.

### 2026-08-06 — Phase 10: Data pipelines and persistence

Closed the path from a raw export to a queryable processed series. Ingest
validates hard, quarantines on failure, and stamps a content-addressed
`data_revision`. Transform resolves re-measurements without deleting rows,
normalises units only through the declared registry, and publishes atomically
to Parquet plus the measurement repository. Subgrouping stays at the series
boundary so the processed zone keeps site grain.

Fake, DuckDB, and PostgreSQL implement the same ports; contract tests always
run Fake and DuckDB, and PostgreSQL when `SPC_TEST_DATABASE_URL` is set.
Alembic owns the production schema; DuckDB applies the shared DDL on open.
Pipelines never import infrastructure — the script composition root wires
adapters.

**Verified:** `make check` green — all gates including architecture, contract,
integration, e2e, security, and coverage. PostgreSQL adapter tests skip unless
`SPC_TEST_DATABASE_URL` is set.

**Next:** Phase 11 — application use cases, API, and CLI.

### 2026-08-05 — Phase 9: SPC analytics engine

Closed the statistical core. Most of the chart, rule, capability, MSA, and
variance packages were already in tree and green; this session finished the
tail of the recommended order — spatial classification, the detection
scorecard harness, the performance budget, and the validation write-up.

`analytics/spatial/` classifies a wafer field as radial, edge, asymmetric, or
**none**, with none the default. Edge is decided from structure in the radial
residuals so a bowl cannot beat a ring on a raw correlation contest. The
geometric predictors deliberately do not share code with the generator
(ADR-0021). Five-site plans are refused: they confound radial with edge and
overfit noise.

`analytics/scoring/` scores detections against known onsets without importing
`simulation/`. Detector registries and activation gates (FR-AD01 – FR-AD04)
remain proposed and unimplemented. The scorecard is verified on hand-counted
cases before it is trusted to score the engine.

Against 200 seeded 1.5σ and 3σ step shifts, Western Electric detection rate is
100%; localisation within ±3 points is 99% at 3σ. ARL₀ stays within ±15% of
theory. One thousand points with Nelson's full set stay under the 50 ms budget.
Figures are published in `docs/validation/detection-performance.md`.

**Next:** Phase 10 — data pipelines and persistence.

### 2026-08-04 — Phase 8: Synthetic fab data generator

Built the instrument the rest of the project is scored on. `data/reference/`
grew from a gate-module slice to a full fab — 12 steps, 26 parameters, 27
process tools across 80 chambers, 15 gauges, 3 devices, 6 control plans — and
`src/spc_platform/simulation/` turns it into measurements through a nested
variance model, per-parameter sampling plans, and systematic spatial
signatures. Eight faults are injected unlabelled with a manifest recording
kind, scope, onset, and magnitude.

Two `import-linter` contracts make the generator a two-way leaf. The one that
matters is the ban on reaching `analytics/`: shared code between the generator
and the analytics under test would cancel its own errors and make every
detection score look excellent ([ADR-0021](DECISION_LOG.md#adr-0021)). So
`simulation/validators.py` re-derives statistics `analytics/` will also
compute, on purpose.

The tests earned their place. Four defects surfaced that the gates could not
have caught: a content digest that hashed strings by memory address, making the
reproduction guarantee vacuous; outlier injection multiplied by the chamber
count; Poisson counts remeasured with Gaussian noise, giving 20.4 defects on
remeasured wafers; and a benchmark that timed the generator with `tracemalloc`
running and under-reported throughput by 6.6×. Each would have shown up in
Phase 9 as an inexplicable detection score rather than as a failure.

Also found that mypy had been stopping at a `conftest.py` name collision and
silently skipping `src/` for two phases. Fixing the configuration surfaced a
backlog of type errors, now cleared.

**Verified:** `make check` green — 252 tests, 12 contracts, 93% coverage. The
default 500-lot dataset builds 226,261 rows in 1.8 s at 153 MiB and passes 153
statistical checks; three characteristics are reported as unchecked because
they carry the faults and have no clean quantity to compare.

**Next:** Phase 9 — SPC analytics engine, scored against these manifests.

### 2026-08-04 — Phase 7: Domain model and configuration

Implemented the fab vocabulary as frozen Pydantic types under
`src/spc_platform/domain/`, with `SpecificationLimit` and `ControlLimit` kept
structurally non-interchangeable — no conversion methods, no overlapping
constructor fields, and tests that reject cross-shaped payloads. Measurement
carries unit, timezone-aware timestamp, chamber, and metrology tool; sites
outside the wafer radius and slots outside 1..25 raise at construction.

Typed configuration loads `configs/base/` plus an environment overlay into
immutable settings; an unknown key fails validation (FR-CF02). The unit
registry permits only declared conversions. Committed reference data under
`data/reference/` describes a minimal gate-module slice the Phase 8 generator
will expand. Pandera schemas for the three data zones live in
`pipelines/schemas/` and reject unknown columns, out-of-range slots, and sites
outside the wafer.

Also closed a Phase 6 documentation gap: ADR-0020 (one gate script for local
and CI) is now in the decision log, which was the broken anchor `make check`
had been failing on.

**Verified:** `make check` green — 64 unit tests, `import-linter` reports
domain self-contained, domain coverage ~94%.

**Next:** Phase 8 — synthetic fab data generator.

### 2026-08-04 — Phase 5: Module design

Wrote [MODULE_DESIGN.md](MODULE_DESIGN.md) and ten module specifications in
[modules/](modules/), decomposing the platform into the ten modules the user
specified: ingestion, preprocessing, SPC engine, capability, KPI and trend,
anomaly detection, root cause, change control simulation, dashboard and
reporting, and utilities and configuration.

The decomposition had to be reconciled with the existing hexagonal
architecture, and the reconciliation is the most consequential thing in the
document. **A module is a capability slice, not a package.** Ten top-level
packages named after the ten modules would put statistical computation,
orchestration, and I/O inside one import unit and break the inward-only rule
that `import-linter` is meant to enforce. So modules decompose *responsibility*
and layers continue to decompose *dependency*, with each module specification
naming the layer each of its parts lands in. The module dependency graph is
acyclic and is intended to become `import-linter` contracts in Phase 6.

Four of the ten modules reach past the requirement baseline, and that gap is
recorded rather than filled. Twenty **proposed** identifiers — FR-K01 – FR-K06,
FR-AD01 – FR-AD04, FR-RC01 – FR-RC04, FR-CC01 – FR-CC06 — are listed as
proposals in `MODULE_DESIGN.md` §5 and in each affected module. None is in the
PRD, none carries a priority, and nothing may be built against them until the
PRD is amended. That is now open question Q5.

Two boundaries were held rather than proposed away. **Module 7 assembles
root-cause evidence and never asserts a cause** — `EvidenceBundle` has no
attribute in which a cause could be stored, and a cause reaches the record only
through an attributed human disposition. That keeps the architecture's
automated-root-cause non-goal intact while still delivering commonality,
matched-tool comparison, variance decomposition, and spatial signature as
evidence. **Module 6 delivers the detector contract and the ground-truth scoring
harness**, while multivariate SPC and drift forecasting stay gated behind
Phase 15. The contract is what a future model must satisfy to enter through the
audited path rather than beside it.

The user's Phase 5 definition superseded the roadmap's Toolchain label, as the
Phase 4 definition did last session. Toolchain and CI is now Phase 6, Phases
6–14 became 7–15, and milestones M5–M14 became M6–M15 with M5 now the module
design baseline. **M9 is now the milestone that matters** — the analytics engine
validation, previously M8. Propagated across the roadmap, PRD, progress
tracker, README, structure document, changelog, risk register, decision log,
four status headers, and one Cursor rule.

**Next:** Phase 6, starting with `pyproject.toml` and the `uv` environment.

### 2026-08-04 — Phase 4: Cursor rules

Created one lightweight global `.mdc` rule and six path-scoped specialist rules
under `.cursor/rules/`: project core, product manager, semiconductor quality
engineer, senior Python architect, testing engineer, GitHub maintainer, and
documentation writer. The core supplies only source-of-truth routing,
uncertainty handling, and universal safety constraints. Specialist instructions
activate only for relevant paths.

The specialist rules encode the project's dangerous boundaries rather than
generic job descriptions: control limits remain distinct from specifications;
capability requires stability and a named estimator; numerical truth comes only from
NIST/SEMATECH and Montgomery; dependencies point inward; statistical snapshots
are prohibited; CI cannot hide failures; and documentation cannot claim
compliance or production readiness without evidence.

This activation model is intentional: loading all specialist roles globally
would consume context on unrelated tasks and create conflicting instructions.
One minimal core plus narrow specialists reduces token use and makes the active
role deterministic from the file being changed.

The user's Phase 4 definition superseded the roadmap's prior Toolchain label.
Cursor rules are now Phase 4 and Toolchain/CI is Phase 5; Phases 6–14 did not
move. M4 and M5 were updated accordingly across the PRD, roadmap, progress
tracker, README, structure document, and changelog.

**Next at close:** Toolchain/CI; subsequently moved to Phase 6 when the user
defined module design as Phase 5.

### 2026-08-04 — Phase 3: product requirements
Wrote [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md), the enterprise PRD.
Seventy-four functional and 43 non-functional requirements, each with an
identifier and a priority, plus acceptance criteria in Given/When/Then form for
the behaviours where getting it wrong is most costly.

Two things shaped the document more than the template did. First, **business
objectives BO-1 and BO-2 are deliberately stated as a pair** — detect real
excursions, and keep the false-alarm rate low enough that engineers still trust
the alarm. Either alone is trivially satisfiable by signalling on everything or
on nothing, and only the pair describes a system anyone would actually use.
Second, the acceptance criteria specify the **refusals** as explicitly as the
features: no chart without a qualified baseline, no capability index on an
unstable process, no statistic without its estimator and sample size. Those are
the requirements most likely to be quietly softened into a helpful default
during implementation (R-21), so they are written where a test can enforce them.

Milestone **M8** (analytics engine validated; renumbered to M9 in Phase 5) is
called out as the one that
matters — it is where the project's central claim stops being a plan and
becomes evidence.

This inserted a new phase, so the roadmap renumbered: the former Phases 3–13
are now 4–14, and the fourteen milestones M1–M14 map one-to-one onto them.
Propagated across the roadmap, README, structure document, changelog, and the
status headers of six documents. Two pre-existing phase-reference errors
surfaced during the sweep and were corrected — `DATASET_GUIDE` and
`TESTING_STRATEGY` had both been pointing at the wrong phase since Phase 2,
which is R-12 arriving on schedule.
**Next at close:** Toolchain/CI; subsequently moved to Phase 5 when the user
defined Cursor rules as Phase 4.

### 2026-08-04 — Wafer map rendering decided
Q4 resolved as [ADR-0018](DECISION_LOG.md#adr-0018): interactive Plotly is the
primary wafer map visualisation, static images are export artefacts only. The
deciding requirement is drill-down — a static image can show a pattern but
cannot answer "which wafer, and what was the value?", which is the question
that follows within seconds of noticing one.

Two failure modes were designed out rather than left to be discovered in
review, and both are recorded as new risk **R-43** because they are correctness
issues, not styling ones. **Per-wafer colour autoscaling** makes a wafer varying
by 0.2 nm look identical to one varying by 20 nm, destroying the cross-wafer
comparison the screen exists to support. **Perceptually non-uniform colour maps**
(rainbow, jet) introduce sharp perceived boundaries across smooth data,
manufacturing an apparent edge ring that is not in the measurements — the
rendering fabricating exactly the signature it is meant to detect.

Also settled: a `WaferMapView` value object as the seam, so the interactive
figure and the static report export are two renderings of one computation and
cannot disagree; a ~5 000 marker point budget with an explicit, labelled
degradation to an aggregated view; and cache keys including data and
configuration revision so a recalculated baseline invalidates automatically.

R-42 narrowed to Plotly rendering performance at high point counts, which is
the genuine residual and is bounded by the point budget.
**Next:** the toolchain phase, starting with `pyproject.toml` and the `uv`
environment.

### 2026-08-04 — SEMI standards alignment (Layer 3 expanded)
Layer 3 of [ADR-0017](DECISION_LOG.md#adr-0017) expanded from equipment
communication standards alone to the full set relevant to a fab: E10 (equipment
state / RAM), E79 (productivity, OEE), E90 (substrate tracking), E120/E125
(equipment model), E142 (substrate mapping), E148 (time synchronisation), plus
SECS/GEM and EDA. New document
[domain/SEMI_STANDARDS_ALIGNMENT.md](domain/SEMI_STANDARDS_ALIGNMENT.md) records
the full treatment; `SYSTEM_ARCHITECTURE.md` gains §9 summarising the three
alignments with real architectural consequences.

Those three are worth noting because they are load-bearing rather than
decorative: **E120/E125** are why equipment is modelled as a tool → chamber
hierarchy and `chamber_id` is a first-class field; **E10** is why `Tool` and
`Chamber` carry state history and why baseline qualification must exclude
engineering time rather than absorbing deliberate experimental variation into
the control limits; **E148** is why every timestamp is timezone-aware, since
clock skew between process and metrology tools produces misordered series that
present as statistical defects but are data integrity defects.

Same restriction as Layer 2: controlled publications, so conceptual alignment
only — nothing reproduced, no numerical test dependency, no conformance
claimed. E79/OEE is explicitly out of scope as a feature (R-10); only the
vocabulary is aligned.
**Next:** the toolchain phase, starting with `pyproject.toml` and the `uv`
environment.

### 2026-08-04 — Statistical reference hierarchy
Q3 resolved and recorded as [ADR-0017](DECISION_LOG.md#adr-0017). The single
list of reference sources in ADR-0004 was separating three different needs that
had been collapsed together, so it is now an explicit three-layer hierarchy:
**NIST/SEMATECH and Montgomery** are the sole authorities for numerical
expectations in `tests/statistical/`; **AIAG** (SPC, MSA) governs terminology,
acceptance bands, and quality-system alignment; **SEMI** standards govern data
model naming and equipment interface conventions.

AIAG and SEMI are excluded as numerical test dependencies — both are
copyrighted commercial publications, and reproducing worked-example data from
them carries a licensing exposure with no offsetting benefit. The
recognition value AIAG brings is available through Layer 2 without reproducing
anything. Layer 1 sources are publicly obtainable, so every numerical assertion
is checkable by any reviewer.

Propagated to eight documents. ADR-0004 was not rewritten — it carries an
amendment pointer to ADR-0017, per the immutability rule for decision records.
**Next:** the toolchain phase, starting with `pyproject.toml` and the `uv`
environment.

### 2026-08-04 — Runtime version decision
Q1 resolved and recorded as [ADR-0016](DECISION_LOG.md#adr-0016): Python 3.13,
pinned exactly, with `requires-python = ">=3.13,<3.14"` and a single-version CI
job rather than a matrix. The application is deployed as a container with the
interpreter baked in, so a supported range would add CI time while producing
signal about a configuration that is never shipped. Adoption of 3.14 is defined
as a scheduled revalidation — running the statistical suite against the new
interpreter and comparing to reference values — not a routine bump.

Toolchain installed locally: `uv python install 3.13` (CPython 3.13.13, managed
by uv, independent of the system 3.14.3) and `uv python pin 3.13`, which writes
the committed `.python-version`. Corrected a Phase 1 defect in the root
`.gitignore`, which had been ignoring `.python-version` — that would have made
the interpreter pin invisible to every other clone.
**Next:** the toolchain phase, starting with `pyproject.toml` and the `uv`
environment.

### 2026-08-03 — Phase 2: documentation
Wrote the full fifteen-document set. Recorded fifteen ADRs covering every
foundational decision made so far. Established the domain vocabulary in
`GLOSSARY.md` so that code, configuration, and UI share one set of terms from
the first line of implementation. Sequencing decision made and recorded: the
synthetic data generator precedes the analytics engine, so detection can be
scored rather than eyeballed.
**Next:** the toolchain phase, starting with `pyproject.toml` and the `uv`
environment.

### 2026-08-03 — Phase 1: project structure
Created the 96-directory structure with per-directory documentation.
Established the hexagonal subdivision under `src/spc_platform/`, the six test
tiers, and the eight data zones. Verified the ignore policy keeps the skeleton
while excluding generated artefacts. Initialised the git repository.
**Next:** Phase 2, the documentation set.

---

**Related:** [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) ·
[MODULE_DESIGN.md](MODULE_DESIGN.md) ·
[CHANGELOG.md](../CHANGELOG.md) ·
[RISK_REGISTER.md](RISK_REGISTER.md) ·
[DECISION_LOG.md](DECISION_LOG.md)
