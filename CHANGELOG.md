# Changelog

All notable changes to this project are recorded here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with one domain-specific amendment:

> **A change to statistical behaviour is a MAJOR version bump, regardless of
> API compatibility.** Changing a sigma estimator, a control limit formula, or
> a run-rule definition retroactively alters the meaning of every historical
> number the platform has produced. That is a breaking change in every sense
> that matters to a quality organisation, even when no function signature
> changes.

Entries affecting statistical behaviour are marked **[STAT]** and state
whether existing baselines, reports, or historical comparisons are
invalidated.

---

## [Unreleased]

### Planned — Phase 13: Reporting, excursion workflow, and audit packages
- Deterministic HTML/PDF reports with provenance headers
- Excursion workflow closure and audit package assembly

---

## [0.12.0] — 2026-08-07

**Phase 12 — Dashboard.** Streamlit screens render application view models
only; Plotly wafer maps and Matplotlib static export share one `WaferMapView`
(ADR-0018). Spec and control limits use distinct visual treatments.

### Added

- Application view models: `ChartView`, enriched `WaferMapView`, alarm queue,
  line overview, tool comparison
- Use cases: `build_chart_view`, `build_alarm_queue`, `build_line_overview`,
  `compare_tools`; `get_wafer_map` applies colour-scale limits and the 5 000
  marker budget with labelled aggregation (FR-S06)
- `analytics/comparison/` — Welch's t-test for matched tool/chamber groups
  (FR-T01)
- Streamlit app under `dashboard/` with eight screens, theme tokens, and
  `make demo`
- Dual-render and no-analytics unit tests; wafer-map performance budget test

### Notes

- Trends screen states Module 5 KPIs are proposed and refuses invented series
- Site SSO remains Phase 14; report/PDF generation remains Phase 13
- Lockfile bumps transitive `gitpython` to 3.1.58 (Streamlit dependency) for
  the security gate

---

## [0.11.0] — 2026-08-06

**Phase 11 — Application layer, API, and CLI.** Seven use cases share one
path for FastAPI and Typer; capability refuses out-of-control windows
(FR-P04); append-only audit covers QA §2.2 events the use cases emit.

### Added

- Application ports: `AuditSink`, `Authorisation`, violation / disposition /
  specification repositories
- Use cases: `evaluate_lot`, `recompute_baseline`, `acknowledge_violation`,
  `record_disposition`, `generate_capability_report`, `run_gauge_study`,
  `get_wafer_map`
- `infrastructure/audit/` — in-memory fake and append-only JSONL file store
- `infrastructure/composition/` — local fake wiring for API and CLI
- FastAPI app under `api/` with `X-Actor-Id` actor injection (no SSO)
- Typer CLI with console script `spc`
- Contract tests for OpenAPI responses and audit record shape; e2e that API
  and CLI agree on `evaluate_lot`

### Notes

- Site SSO / LDAP remains deferred to Phase 14; role checks are a thin
  `Authorisation` port with permit/deny fakes.
- Message queues stay out of scope (TECH_STACK rejects Kafka).
- `httpx2` is required for Starlette's TestClient on the pinned stack.

---

## [0.10.0] — 2026-08-06

**Phase 10 — Data pipelines and persistence.** Raw exports become
analysis-ready series with hard-stop validation, quarantine, lineage, and
storage behind one port (ADR-0008).

### Added

- `pipelines/ingest/` — schema validation, measurement-key uniqueness,
  quarantine artefacts, content-addressed `data_revision`, run records
- `pipelines/transform/` — attach context, resolve re-measurements, unit
  normalisation, atomic processed publish, `build_subgroups` at the series
  boundary
- `pipelines/run.py` — raw-to-processed composition helper (no infrastructure
  imports)
- `infrastructure/readers/` — CSV/Parquet `MeasurementSource`
- `infrastructure/repositories/` — Fake, DuckDB, and PostgreSQL adapters for
  measurements and baselines
- Alembic initial migration under `migrations/` (PostgreSQL); shared DDL used
  by DuckDB
- `scripts/pipelines/run_pipeline.py` — local composition root
- Contract suite parametrised over Fake + DuckDB (+ PostgreSQL when
  `SPC_TEST_DATABASE_URL` is set)

### Notes

- Timestamps are persisted as UTC wall time; domain objects remain
  timezone-aware on read.
- PostgreSQL contract and Alembic round-trip tests skip without
  `SPC_TEST_DATABASE_URL` so clone-and-run stays zero-infrastructure.

---

## [0.9.0] — 2026-08-05

**Phase 9 — SPC analytics engine.** The statistical core the platform's
credibility rests on. Expected values come from NIST/SEMATECH and Montgomery;
snapshotting current output as an expectation is prohibited.

### Added

- `analytics/estimators/` — derived control-chart constants and named
  short-term / long-term sigma estimators
- `analytics/charts/` — I-MR, X̄-R, X̄-S, EWMA, CUSUM, p/np/c/u; Phase I studies
  separate from Phase II panels (`FixedIndividualsLimits`, FR-C03)
- `analytics/rules/` — Western Electric and Nelson from vectorised primitives,
  with measured ARL₀
- `analytics/capability/` and `analytics/msa/` — Cp/Cpk/Pp/Ppk/Cpm; gauge R&R
  by ANOVA, bias, linearity, stability, NDC
- `analytics/variance/` — nested variance decomposition (FR-S07)
- `analytics/spatial/` — radial / edge / asymmetric / none classification
  (FR-S02), with none the default and geometric predictors independent of the
  generator
- `analytics/scoring/` — detection scorecard against known onsets (test
  harness; FR-AD01 – FR-AD04 remain proposed)
- `configs/spc/` chart defaults and named rule sets
- `docs/validation/detection-performance.md` — published ARL₀, detection
  power, and spatial recovery figures
- Statistical tier covering constants, charts, rules, capability, MSA, ARL,
  detection power, spatial recovery, and scoring-harness integrity
- Performance budget test: 1 000 points with Nelson's full set under 50 ms

### Notes

- Detector registries, activation gates, and false-alarm characterisation
  before activation are proposed requirements and are not in this release
- Application use cases that call the analytics layer arrive in Phase 11

---

## [0.8.0] — 2026-08-04

**Phase 8 — Synthetic fab data generator.** The measurement instrument for
every detection claim the platform will make.

Nothing here changes statistical behaviour, because there is no analytics yet.
It does fix the ground truth those analytics will be scored against, so the
generator's own defects — listed under Fixed — would have shown up later as
inexplicably good or bad detection scores rather than as failures.

### Added

- `src/spc_platform/simulation/`: generator configuration models, fab topology,
  nested variance, wafer sampling plans and spatial signatures, fault
  injection, ground-truth manifests, deterministic writers, and independent
  statistical validators
- `data/reference/` expanded to a full fab: 12 process steps, 26 parameters, 27
  process tools across 80 chambers, 15 gauges, 3 devices on 2 nodes, 45
  specification limits, 6 control plans charting 44 characteristics
- Eight fault kinds with ground truth: gradual drift, step shift, variance
  increase, cyclic, single-tool excursion, spatial signature change, metrology
  drift, and outliers — all emitted unlabelled
- `spc_platform/infrastructure/vcs.py` reading the code revision, suffixed
  `-dirty` when the working tree is modified
- `scripts/simulation/` entry points and `make dataset`, `make dataset-check`,
  `make dataset-bench`
- Two `import-linter` contracts pinning the generator as a two-way leaf
- ADR-0021 (the generator is an instrument, not a dependency) and ADR-0022
  (metrology gauge pools live in generator configuration)
- 188 tests across the unit, statistical, integration, and contract tiers,
  including a contract test that the generated frame satisfies the raw-zone
  ingestion schema without either side importing the other

### Fixed

Four generator defects found by the new tests, each of which would have
corrupted the benchmark silently:

- **Content digest hashed string columns by memory address.** Two byte-identical
  frames digested differently, making the reproduction guarantee vacuous.
  Numeric columns are now widened to a canonical dtype and text columns hashed
  as text, so the digest depends on values and order and on nothing else.
- **Outlier injection applied each source once per distinct chamber in a
  block**, with an identical random key each time — multiplying the magnitude by
  the chamber count and over-counting in the manifest. Now scoped to the rows
  that ran in the chamber, once each.
- **Remeasurement re-drew Poisson counts with Gaussian gauge noise**, producing
  fractional defect counts on remeasured wafers only. Counts are now re-drawn as
  counts.
- **The benchmark timed the generator with `tracemalloc` running**, reporting
  6.6× below the real throughput. The footprint is now measured in a separate,
  untimed run.

### Changed

- Messiness is applied loss-first, so every count in the manifest describes the
  dataset delivered rather than an intermediate state — and a result that was
  never recorded is not one anyone sends back to metrology
- `MessinessRecord.remeasured_wafers` renamed to `remeasurement_events`: it
  counts wafer-and-parameter pairs, and one wafer remeasured for two parameters
  is two events
- mypy configured with `explicit_package_bases` so the whole tree is checked;
  the previous configuration stopped at a `conftest.py` name collision and had
  been silently skipping `src/` for two phases
- Ruff `D102` exemption aligned with the existing `D103` exemption for test
  tiers, so grouping tests into a class no longer demands prose that the same
  test at module level does not

---

## [0.7.0] — 2026-08-04

**Phase 7 — Domain model and configuration.** The fab vocabulary as types, and
the typed configuration system every later module will parse once at the
boundary.

### Added

- Domain entities and value objects: lot/wafer/site, tool/chamber/recipe/step,
  parameter, measurement, measurement series, specification and control limits,
  baseline, subgroup, violation, disposition, chart and rule specs
- `SpecificationLimit` / `ControlLimit` separation with structural tests
  (FR-C06) — no conversion path, no overlapping constructor fields
- Common primitives: `SPCPlatformError` hierarchy, unit registry, injectable
  `Clock`, provenance capture
- Layered configuration loader with unknown-key rejection (FR-CF02) and
  configuration revision hashing
- Committed reference data under `data/reference/` for a minimal gate-module
  slice
- Pandera schemas for raw, interim, and processed measurement zones
- ADR-0020 — one gate script for local and CI (referenced by Phase 6, now
  recorded)
- 64 unit tests covering domain invariants, configuration, units/time, and
  zone schemas

### Changed

- `pyproject.toml` version to 0.7.0; mypy `files` scoped to `src/spc_platform`
  to avoid duplicate-module detection under the src layout

---

## [0.6.0] — 2026-08-04

**Phase 6 — Toolchain and CI foundation.** Mechanical quality gates in place
before application logic.

### Added

- `pyproject.toml` with src layout, Python 3.13 pin, and `uv` environment with
  committed `uv.lock`
- Ruff, `mypy --strict`, pytest with per-tier markers
- `import-linter` contracts enforcing the inward-only dependency rule and the
  module dependency graph
- `pre-commit` hooks including `nbstripout` and `gitleaks`
- `Makefile` and GitHub Actions calling the same `scripts/ci/gate.sh`

---

## [0.5.0] — 2026-08-04

**Phase 5 — Module design.** The decomposition of the platform into ten
modules, and the map from those modules onto the hexagonal layers they are
built inside.

### Added

- `docs/MODULE_DESIGN.md` — the module index: what a module is in this project,
  the ten modules at a glance, the dependency graph, the requirement coverage
  map, the recorded scope boundary, and the conventions binding on all ten
- `docs/modules/01-data-ingestion.md` through
  `docs/modules/10-utilities-and-configuration.md` — ten specifications, each
  stating purpose, responsibilities, public interfaces, dependencies, expected
  inputs and outputs, files to create, testing requirements, documentation
  required, and future extension points
- Twenty **proposed** requirement identifiers recorded but not adopted:
  FR-K01 – FR-K06 (KPI), FR-AD01 – FR-AD04 (detector contract and detection
  scoring), FR-RC01 – FR-RC04 (root-cause evidence assembly), and
  FR-CC01 – FR-CC06 (change control simulation). None is in the PRD and nothing
  may be built against them until it is amended
- Open question Q5: whether those twenty proposals are approved
- ADR-0019 — modules are capability slices, not packages: ten top-level
  packages would place computation, orchestration, and I/O in one import unit,
  making `analytics/` impure and the statistical test tier impossible

### Changed

- Module design is Phase 5 and Toolchain/CI moves to Phase 6; the former Phases
  6–14 became 7–15, and milestones M5–M14 became M6–M15. M5 is now the module
  design baseline and **M9** — analytics engine validated — is the milestone
  that matters, previously M8
- Phase numbers, milestone identifiers, and status headers aligned across the
  PRD, roadmap, progress tracker, README, structure documentation, technology
  stack, testing strategy, dataset guide, deployment plan, risk register,
  documentation index, ADR-0015, and `.cursor/rules/product-manager.mdc`
- Phase 6 now scopes `import-linter` contracts to encode the module dependency
  graph as well as the layering rule

### Notes

Two scope boundaries were held rather than expanded. Module 7 assembles
root-cause **evidence** and never asserts a cause, preserving the
automated-root-cause non-goal in `SYSTEM_ARCHITECTURE.md` §10. Module 6
delivers the detector contract and the ground-truth scoring harness, while
model-based detection remains gated behind Phase 15 (R-10).

---

## [0.4.0] — 2026-08-04

**Phase 4 — Cursor rules.** One lightweight global core plus six path-scoped
professional roles that encode the project's product, domain, architecture,
verification, repository, and documentation controls before implementation.

### Added

- `.cursor/rules/project-core.mdc` — the only always-applied rule; minimal
  source-of-truth routing, uncertainty handling, scope discipline, and
  universal safety constraints
- `.cursor/rules/product-manager.mdc` — requirements, user stories, acceptance
  criteria, feature planning, prioritization, and product change control
- `.cursor/rules/semiconductor-quality-engineer.mdc` — semiconductor
  terminology, SPC, capability, MSA, quality systems, root-cause rigor, and
  manufacturing change control
- `.cursor/rules/senior-python-architect.mdc` — Clean Architecture, SOLID,
  dependency inversion, modular Python, design patterns, reuse, and performance
- `.cursor/rules/testing-engineer.mdc` — pytest strategy, test tiers, regression
  evidence, mocking, coverage, and CI behavior
- `.cursor/rules/github-maintainer.mdc` — branch and pull-request policy,
  Conventional Commits, issue quality, GitHub Actions, and repository hygiene
- `.cursor/rules/documentation-writer.mdc` — Markdown, API and architecture
  documentation, ADRs, READMEs, and technical writing

### Changed

- `.cursor/README.md` now records the activation model: one lightweight global
  core and six path-scoped specialist rules
- The roadmap now defines Cursor rules as Phase 4 and Toolchain/CI as Phase 5;
  Phases 6–14 are unchanged
- Milestones M4 and M5, status tables, next actions, and phase references were
  aligned across the PRD, roadmap, progress tracker, README, structure
  documentation, technology stack, testing strategy, and ADR-0015

---

## [0.3.0] — 2026-08-04

**Phase 3 — Product requirements.** The requirement baseline that Phases 4–14
deliver against, plus the decisions settled while writing it.

### Added
- `docs/PRODUCT_REQUIREMENTS.md` — the enterprise PRD. Six business objectives
  with measurable criteria; product metrics separated from engineering metrics;
  five personas; 74 functional requirements across eleven areas and 43
  non-functional requirements across eight categories, each identified and
  prioritised; four user story epics; Given/When/Then acceptance criteria for
  the highest-risk behaviours, including the refusals; constraints,
  dependencies, technical risks, future roadmap, fourteen milestones, and a
  four-level definition of done
- `docs/domain/SEMI_STANDARDS_ALIGNMENT.md` — which SEMI standards shape the
  vocabulary, equipment model, and data conventions, and what is explicitly not
  claimed
- `docs/SYSTEM_ARCHITECTURE.md` §9 — SEMI standards alignment, covering the
  three with concrete architectural consequences (E120/E125 equipment
  hierarchy, E10 equipment state, E148 time synchronisation)
- `docs/GLOSSARY.md` §7 — equipment state (E10), OEE (E79), substrate tracking
  (E90), substrate mapping (E142), and time synchronisation (E148)

### Changed
- `docs/RISK_REGISTER.md` — R-42 narrowed to Plotly rendering performance, with
  the point budget, `WaferMapView` seam, and cache-invalidation rule as
  mitigations; new **R-43** covering visualisation that fabricates a spatial
  signature (High, 12); summary table corrected and now 23 risks
- `dashboard/README.md`, `reports/README.md`, and the dashboard phase of
  `docs/DEVELOPMENT_ROADMAP.md` — wafer map rendering requirements and exit
  criteria
- **Roadmap renumbered from 13 phases to 14.** Product requirements inserted as
  Phase 3; the former Phases 3–13 became 4–14. Milestones M1–M14 map one-to-one
  onto phases. Propagated to `README.md`,
  `docs/architecture/repository-structure.md`, `docs/PROJECT_PROGRESS.md`, and
  the status headers of six documents
- `docs/DATASET_GUIDE.md` and `docs/TESTING_STRATEGY.md` — corrected phase
  references that had been wrong since Phase 2, independently of the
  renumbering

### Decisions recorded
- **ADR-0018 (2026-08-04)** — Interactive Plotly wafer maps as the primary
  visualisation; static images as export artefacts only. Establishes the
  `WaferMapView` seam shared by screen and report, fixed colour scale limits
  across comparison sets, perceptually uniform colour maps only, a ~5 000 marker
  point budget with labelled degradation, and revision-keyed cache
  invalidation. Resolves Q4.
- **ADR-0017 (2026-08-04)** — Three-layer reference hierarchy. NIST/SEMATECH
  and Montgomery are the sole authorities for numerical expectations in
  `tests/statistical/`; AIAG (SPC, MSA) governs terminology, acceptance bands,
  and quality-system alignment; SEMI standards (E10, E79, E90, E120/E125, E142,
  E148, SECS/GEM, EDA) govern the equipment model, equipment state semantics,
  substrate and timestamp conventions, and interface design. AIAG and SEMI are
  excluded as numerical test dependencies on licensing grounds. Narrows
  ADR-0004.
- **ADR-0016 (2026-08-04)** — Python 3.13 pinned exactly, single supported
  version. `requires-python = ">=3.13,<3.14"`, single-version CI rather than a
  matrix. Adoption of 3.14 is defined as a scheduled revalidation exercise
  against the statistical reference suite, not a routine dependency bump.

---

## [0.2.0] — 2026-08-03

**Phase 2 — Project documentation.** The complete documentation set, written
before implementation so that architecture, standards, and domain vocabulary
are settled rather than emergent.

### Added

**Domain and context**
- `docs/PROJECT_CONTEXT.md` — the problem, the users, the failure modes of
  existing tooling, scope boundaries, and success criteria
- `docs/GLOSSARY.md` — the authoritative vocabulary spanning manufacturing
  hierarchy, metrology, SPC, capability, variance structure, and quality system

**Technical design**
- `docs/SYSTEM_ARCHITECTURE.md` — layering, component responsibilities, data
  flow, runtime sequences, deployment topology, scale envelope, and explicit
  non-goals
- `docs/TECH_STACK.md` — every technology selection with the alternatives
  rejected and the reasoning
- `docs/DECISION_LOG.md` — 15 architecture decision records

**Engineering discipline**
- `docs/CODING_STANDARDS.md` — five non-negotiable rules, style, typing, error
  handling, naming, and rules specific to AI-generated code
- `docs/TESTING_STRATEGY.md` — six test tiers and the five verification methods
  of the statistical tier

**Data and quality system**
- `docs/DATASET_GUIDE.md` — data zones, measurement model, synthetic generator
  design with its nested variance structure, and injected fault catalogue
- `docs/QUALITY_ASSURANCE_PLAN.md` — quality objectives, IATF 16949 / ISO 9001
  mapping, ALCOA+ data integrity, gates, and change control

**Planning and operations**
- `docs/DEVELOPMENT_ROADMAP.md` — 13 phases with deliverables and demonstrable
  exit criteria
- `docs/RISK_REGISTER.md` — 22 scored risks with mitigations and triggers
- `docs/PROJECT_PROGRESS.md` — living status document
- `docs/DEPLOYMENT_PLAN.md` — on-premises deployment, container strategy,
  scheduled jobs, observability, and disaster recovery
- `CHANGELOG.md` — this file

### Changed
- Root `README.md` expanded into the full project entry point
- `docs/README.md` now indexes the documentation set

### Decisions recorded
ADR-0001 through ADR-0015, covering the src layout, hexagonal architecture,
the specification/control limit type separation, the statistical test tier,
in-house SPC mathematics, Streamlit, uv, the DuckDB/PostgreSQL split,
declarative configuration, synthetic data with injected faults, audit trail
separation, arrays versus DataFrames, the modular monolith, the on-premises
assumption, and documentation-before-implementation.

---

## [0.1.0] — 2026-08-03

**Phase 1 — Project structure.** The production-ready folder structure and its
rationale. No application logic.

### Added
- 96-directory structure across 13 top-level folders
- src layout at `src/spc_platform/` with hexagonal subdivision: `domain`,
  `analytics`, `application`, `pipelines`, `infrastructure`, `api`, `cli`,
  `config`, `observability`, `common`
- Six test tiers with statistical validation separated: `unit`, `integration`,
  `e2e`, `statistical`, `contract`, `performance`, plus `fixtures` and
  `factories`
- Eight data zones implementing a one-directional flow: `raw`, `external`,
  `interim`, `processed`, `synthetic`, `reference`, `schemas`, `archive`
- `.cursor/` structure for rules, context, commands, skills, and prompts
- `.github/` structure for workflows, composite actions, and templates
- README in every top-level directory explaining its purpose and rules
- `docs/architecture/repository-structure.md` — canonical structure rationale
- Scoped ignore policy: source and contracts committed; data, logs, model
  binaries, and generated reports excluded; directory skeleton preserved
- Git repository initialised on `main`

### Verified
- Test artefacts in `data/raw/`, `logs/app/`, `models/artifacts/`, and
  `reports/generated/` confirmed ignored
- Directory skeleton and documentation confirmed tracked

---

[Unreleased]: https://keepachangelog.com/en/1.1.0/
