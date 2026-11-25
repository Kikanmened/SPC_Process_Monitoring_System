# Semiconductor Manufacturing SPC Monitoring Platform

A Statistical Process Control monitoring platform for semiconductor wafer
fabrication — built to the engineering standard of an internal fab analytics
tool rather than a demonstration project.

> **Status: Phases 1–14 complete (release 0.14.0) — on-prem reference stack implemented.**
> Domain, analytics, pipelines, API/CLI, dashboard, reports, and Docker Compose
> operations are in place. Phase 15 (advanced analytics) is stretch and gated.
> See [PROJECT_PROGRESS.md](docs/PROJECT_PROGRESS.md).

This status describes implemented scope, not qualification for production use
or evidence that an arbitrary commit has passed CI. Verify the exact revision
using the checks under [Verification evidence](#verification-evidence).

**Deployment assumption:** on-premises Docker Compose; **no public cloud** at
runtime ([ADR-0014](docs/DECISION_LOG.md#adr-0014), CON-2). Fab process data
must not leave the site. All repository data is synthetic.

---

## The problem

A wafer fab measures thousands of process parameters continuously. A 300 mm lot
carries 25 wafers, each measured at 5 to 49 sites, across hundreds of process
steps on dozens of tools. The question asked of that data is simple to state
and difficult to answer well:

> **Is this process behaving as it should — and if not, what changed?**

Answering it badly is expensive in both directions. A missed excursion sends
defective material through a process flow that takes weeks to complete. A false
alarm stops a healthy tool, and — worse — teaches operators to dismiss alarms.
A system that cries wolf is worse than no system.

This platform is built around the failure modes that make most SPC tooling
untrustworthy: conflating control limits with specification limits, ignoring
the nested variance structure of wafer data, reporting capability without
qualifying stability or naming the estimator, trusting unqualified metrology,
and enabling every run rule at once.

## What it does

| Capability | Detail |
|---|---|
| **Control charting** | I-MR, X̄-R, X̄-S, EWMA, CUSUM, and attribute charts (p, np, c, u), selected per parameter class rather than applied uniformly |
| **Run-rule detection** | Configurable Western Electric and Nelson rule sets, with the false-alarm cost of each configuration measured, not assumed |
| **Process capability** | Cp, Cpk, Pp, Ppk, Cpm — with short-term and long-term sigma treated as the different things they are, and stability required first |
| **Measurement system analysis** | Gauge R&R by ANOVA, bias, linearity, stability, NDC — because a chart is only as trustworthy as the gauge behind it |
| **Variance decomposition** | Nested separation of within-wafer, wafer-to-wafer, and lot-to-lot contributions, so improvement effort targets the dominant term |
| **Spatial analysis** | Wafer maps and radial/edge signature detection — patterns invisible in a time series that often carry the root cause |
| **Tool and chamber matching** | The most common source of an apparent process shift is a tool-to-tool offset, not the process |
| **Excursion workflow** | Alarm acknowledgement, OCAP linkage, disposition, and an append-only audit trail |
| **On-prem operations** | Compose stack (API, dashboard, scheduler), health/metrics, idempotent jobs, tested backup/restore |

## Dashboard tour

The Streamlit interface follows the investigation sequence used by metrology,
process, and quality engineers: establish stability, evaluate capability,
localise variation, and confirm that the measurement system can be trusted.
The bundled demo uses synthetic fab data and in-process adapters, so these
views run without a database or external services.

### 1. Control chart — Is the process stable?

The control-chart view overlays Phase II control limits and specification
limits without conflating them. Every chart includes its estimator, baseline,
sample count, analysis window, and data/configuration revisions.

![Phase II individuals control chart for oxide thickness](dashboard/assets/screenshots/control-chart.png)

### 2. Capability — Can the stable process meet specifications?

Capability indices are reported only after the process has passed the
stability gate. The view distinguishes potential capability (Cp/Cpk) from
overall performance (Pp/Ppk) and names the sigma estimator, sample count, and
analysis window behind each result.

![Capability analysis for a stable oxide-thickness process](dashboard/assets/screenshots/capability-analysis.png)

### 3. Wafer map — Where is the variation occurring?

The wafer-map view plots measurements at true site coordinates, preserves the
wafer boundary, edge exclusion, and notch, and makes the colour-scale mode and
numeric range explicit. The same typed view can be exported as a static PNG for
reports and audit packages.

![Wafer map for oxide thickness with fixed colour scale](dashboard/assets/screenshots/wafer-map.png)

### 4. Gauge R&R — Can the measurement system be trusted?

The MSA workspace runs a crossed ANOVA Gauge R&R study against configured
acceptance bands and reports study variation, the decision criterion, and the
number of distinct categories (NDC).

![Gauge R&R measurement-system analysis dashboard](dashboard/assets/screenshots/msa-gauge-rr.png)

## Scientific scope and non-claims

This repository demonstrates statistical methods and software controls using
synthetic semiconductor data. Its conclusions are deliberately bounded:

- **Synthetic evidence is not factory evidence.** Injected faults make
  detection rate, latency, localisation, and false-alarm behaviour measurable
  under the generator's assumptions. They do not establish sensitivity on a
  particular process, tool fleet, product, or fab.
- **Detected patterns are not proven causes.** A rule violation, spatial
  signature, or tool offset is evidence for investigation. The platform does
  not confirm plasma physics, equipment failure, or causal root cause.
- **An MSA calculation is not metrological traceability.** Gauge R&R, bias,
  linearity, stability, and NDC results describe supplied study data. They do
  not prove calibration status, uncertainty, reference-material suitability,
  or laboratory accreditation.
- **Capability is conditional.** Capability results are refused when the
  evaluated window is unstable, but an in-control result does not by itself
  prove distributional fit, sampling representativeness, or future product
  conformity.
- **The software is decision support, not process control.** It does not issue
  recipe changes, actuate equipment, release material, or replace an approved
  control plan, OCAP, engineering review, or quality-system disposition.
- **Standards alignment is not certification.** References to IATF 16949,
  AIAG, VDA, or SEMI describe vocabulary and design alignment; they do not
  claim certification, customer approval, or validation for a regulated
  production environment.

## What makes it different

**Statistical implementations are checked against evidence outside the
implementation.** `tests/statistical/` is a separate test tier with its own CI
stage. Numerical expectations come from cited NIST/SEMATECH and Montgomery
examples, hand-computed cases, analytical invariants, or seeded simulation.
Snapshotting current output as an expected value is prohibited because it
would preserve the implementation's existing error.

**Detection is scored against ground truth.** All data is synthetic, generated
with a nested, physically motivated variance structure and deliberately
injected faults of known type, magnitude, and onset. That makes detection rate,
detection latency, localisation accuracy, and false-alarm rate measurable for
the simulated scenarios. Real production data rarely provides equally complete
labels, and performance on the generator must not be presented as field
performance.

**The defining SPC error is blocked in the typed application path.**
`SpecificationLimit` and `ControlLimit` are distinct types with no conversion
between them. Repository tests reject cross-shaped payloads; this protects the
platform boundary without claiming that external data or downstream consumers
are automatically correct.

**False alarms are treated as defects.** Measured ARL₀ is asserted against
theory within ±15%. Sensitivity and false-alarm rate are both acceptance
criteria, because either alone is trivially satisfiable.

**Every emitted analytical result is designed to be traceable.** Data revision,
code revision, and configuration revision travel with charts, capability
results, and reports. Traceability identifies inputs and logic; it does not by
itself establish that either was scientifically appropriate.

**Cloud is excluded by design.** The stack runs on-prem with no managed cloud
runtime dependency, matching how fabs actually handle confidential process
data ([DEPLOYMENT_PLAN.md](docs/DEPLOYMENT_PLAN.md)).

## Verification evidence

Verification is organised by the kind of confidence it provides. No single
test count or coverage percentage is treated as proof of scientific validity.

| Question | Evidence in this repository | What it does not establish |
|---|---|---|
| Are numerical implementations correct on known cases? | Cited published examples, hand calculations, property-based invariants, and deterministic tests in `tests/statistical/` | Correctness outside the tested assumptions and parameter ranges |
| Are alarm characteristics plausible under controlled conditions? | Seeded ARL₀/ARL₁ studies and scoring against faults with known onset and magnitude | Detection performance on real fab data or proof of physical causality |
| Are invalid analyses refused? | Tests for absent baselines, unstable capability windows, insufficient designs, invalid units, and malformed boundary payloads | That every possible misuse or upstream data-quality failure has been anticipated |
| Do system boundaries behave consistently? | Unit, contract, integration, end-to-end, migration, and repository-adapter tests | Production availability, disaster recovery objectives, or site-specific infrastructure qualification |
| Are dependency and architecture rules enforced? | Ruff, `mypy --strict`, `import-linter`, Bandit, dependency audit, secret scanning, and documentation-link checks | A complete security assessment, penetration test, or supply-chain guarantee |
| Do dashboards communicate the tested results? | Assertions on chart/view data plus the reviewed captures above | Pixel-perfect rendering, complete accessibility certification, or correct human interpretation |

Run the evidence against the exact checkout rather than relying on the presence
of workflow files or on an old test count:

```bash
make install   # reproduce the locked Python 3.13 environment
make check     # format, lint, types, architecture, docs, all test tiers, security, coverage
```

`make check` and GitHub Actions call the same gate definitions in
[`scripts/ci/gate.sh`](scripts/ci/gate.sh). A workflow configuration is not a
pass result: for a public claim, cite the green check for the exact commit or
publish a dated verification record with the command, environment, revision,
and result. The full rationale, reference hierarchy, coverage policy, and known
test exclusions are documented in
[`TESTING_STRATEGY.md`](docs/TESTING_STRATEGY.md).

## Documentation

| Read this | To answer |
|---|---|
| [PROJECT_CONTEXT.md](docs/PROJECT_CONTEXT.md) | What problem is this, who is it for, what is out of scope? |
| [PRODUCT_REQUIREMENTS.md](docs/PRODUCT_REQUIREMENTS.md) | What exactly must it do, and how will we know it does? |
| [SYSTEM_ARCHITECTURE.md](docs/SYSTEM_ARCHITECTURE.md) | How is it built, and where does anything live? |
| [GLOSSARY.md](docs/GLOSSARY.md) | What does this term mean, precisely? |
| [TECH_STACK.md](docs/TECH_STACK.md) | What are we using, and what did we reject? |
| [CODING_STANDARDS.md](docs/CODING_STANDARDS.md) | How must code be written here? |
| [TESTING_STRATEGY.md](docs/TESTING_STRATEGY.md) | How do we know the numbers are right? |
| [DATASET_GUIDE.md](docs/DATASET_GUIDE.md) | What is the data model, and where does data come from? |
| [QUALITY_ASSURANCE_PLAN.md](docs/QUALITY_ASSURANCE_PLAN.md) | How does this fit an IATF 16949 quality system? |
| [DECISION_LOG.md](docs/DECISION_LOG.md) | Why is it done this way? |
| [DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) | What is the plan, and what does "done" mean? |
| [RISK_REGISTER.md](docs/RISK_REGISTER.md) | What could go wrong, and what are we doing about it? |
| [DEPLOYMENT_PLAN.md](docs/DEPLOYMENT_PLAN.md) | How does it reach a fab and stay running? |
| [PROJECT_PROGRESS.md](docs/PROJECT_PROGRESS.md) | Where are we right now? |
| [CHANGELOG.md](CHANGELOG.md) | What changed, and when? |

New to the project? Read `PROJECT_CONTEXT`, then `SYSTEM_ARCHITECTURE`, then
`GLOSSARY`. That is enough to contribute. For current status, start with
`PROJECT_PROGRESS`.

## Repository layout

```
src/           Application source — the only importable code
dashboard/     Operator and engineer interface
data/          Immutable data zones: raw → interim → processed
notebooks/     Exploration and statistical methodology
tests/         Verification, incl. a dedicated statistical tier
docs/          Architecture, domain, and quality-system documentation
scripts/       Automation, operations, and the synthetic fab generator
configs/       Declarative SPC and process configuration
models/        Statistical baselines and model registry
reports/       Generated quality deliverables
logs/          Runtime logs and the audit trail
.cursor/       AI development environment
.github/       CI quality gates and templates
```

Every directory carries a README explaining its purpose and its rules. Full
rationale in
[docs/architecture/repository-structure.md](docs/architecture/repository-structure.md).

## Architecture in one diagram

```mermaid
graph LR
    UI[dashboard · api · cli · scheduler] --> APP[application<br/>use cases · ports]
    APP --> DOM[domain<br/>entities · invariants]
    APP --> ANA[analytics<br/>SPC · capability · MSA]
    ANA --> DOM
    APP -.ports.-> INF[infrastructure<br/>DuckDB · PostgreSQL · files]
    INF --> DOM
```

Dependencies point inward, always. `domain/` imports nothing from this
repository; `analytics/` imports only `domain/` plus NumPy, SciPy, and
statsmodels. The rule is enforced by `import-linter` in CI, not by convention.

## Technology

Python 3.13 · NumPy · SciPy · statsmodels · pandas · Pandera · Pydantic v2 ·
DuckDB · PostgreSQL + TimescaleDB · FastAPI · Streamlit · Plotly · uv · Ruff ·
mypy · pytest · Hypothesis · Docker Compose · GitHub Actions

Selections and rejected alternatives in [TECH_STACK.md](docs/TECH_STACK.md).

## Getting started

**No Docker (clone-and-run dashboard):**

```bash
make install   # uv sync --frozen --all-groups
make check     # full quality gate set (same as CI)
make demo      # Streamlit UI with in-process fakes
```

Dashboard: [http://localhost:8501](http://localhost:8501)

**Full on-prem stack (API + dashboard + scheduler):**

```bash
make install
make stack     # docker compose up --build -d
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
```

- API health: [http://localhost:8000/health](http://localhost:8000/health)
- Dashboard: [http://localhost:8501](http://localhost:8501)
- Stop: `make stack-down`

Ops proof points: `make jobs` (idempotent double-run), `make backup`.
Runbooks live under [docs/runbooks/](docs/runbooks/). Deployment design:
[DEPLOYMENT_PLAN.md](docs/DEPLOYMENT_PLAN.md).

A reviewer can clone and see working control charts within minutes with no
database and no containers (`make demo`). That is why the storage layer sits
behind a port. The Compose path is the fab-shaped deployment profile.

## Roadmap

| Phase | Scope | Status |
|---|---|---|
| 1 | Project structure | ✅ Complete |
| 2 | Project documentation | ✅ Complete |
| 3 | Product requirements | ✅ Complete |
| 4 | Cursor rules | ✅ Complete |
| 5 | Module design | ✅ Complete |
| 6 | Toolchain and CI foundation | ✅ Complete |
| 7 | Domain model and configuration | ✅ Complete |
| 8 | Synthetic fab data generator | ✅ Complete |
| 9 | SPC analytics engine | ✅ Complete |
| 10 | Data pipelines and persistence | ✅ Complete |
| 11 | Application layer, API, CLI | ✅ Complete |
| 12 | Dashboard | ✅ Complete |
| 13 | Reporting, excursion workflow, audit packages | ✅ Complete |
| 14 | Deployment and operations | ✅ Complete (0.14.0) |
| 15 | Advanced analytics | Stretch (gated) |

Deliverables and exit criteria per phase in
[DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md); requirements and
milestones in
[PRODUCT_REQUIREMENTS.md](docs/PRODUCT_REQUIREMENTS.md); the ten modules and
their interfaces in [MODULE_DESIGN.md](docs/MODULE_DESIGN.md).

## Context

Built as a portfolio project for semiconductor quality engineering, targeting
the competency profile of an Advanced Quality Excellence Engineer in a European
automotive-facing fab: applied statistics, semiconductor process knowledge,
quality-system fluency (IATF 16949, MSA, control plans, 8D/CAPA), and the
software engineering discipline that makes analytics trustworthy in production.

**All data is synthetic.** No confidential process data, customer device
information, or proprietary fab parameters appear anywhere in this repository.
