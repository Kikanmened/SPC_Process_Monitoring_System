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

### Planned — Phase 8: Synthetic fab data generator
- Fab model with nested variance structure and systematic spatial signature
- Ground-truth fault injection with manifests
- Byte-identical regeneration from config + seed + code revision

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
