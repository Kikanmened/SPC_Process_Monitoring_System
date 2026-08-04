# Repository Structure and Rationale

**Status:** Active — structure established, no application logic yet.
**Audience:** engineers joining the project, and the Cursor agent.

This is the canonical explanation of how the repository is organised and why.
Each top-level directory also carries its own README with detail; this document
is the map that makes those readable in relation to one another.

---

## The three design forces

Every decision below serves one of three goals.

**1. Correctness must be provable, not asserted.**
This platform decides whether a wafer lot is behaving normally. A wrong control
limit does not throw an exception — it passes bad material or halts a healthy
tool, and it does so quietly. So statistical logic is isolated in one pure
layer, and validated separately against cited references.

**2. Process knowledge changes faster than code.**
New tools are qualified, limits are recalculated, rule sets are tuned. That
knowledge is declarative and reviewable (`configs/`, `data/reference/`) so a
quality engineer can change it without a code release, and every change carries
an author and a reason.

**3. The AI agent is a first-class contributor.**
Structure is chosen so the agent can locate the right file from the path alone
and load a small, sufficient context. `.cursor/` and `docs/` exist so
architecture is *read*, never re-inferred.

---

## Top-level map

```
SPC_Process_Monitoring_System/
├── src/           Application source — the only importable code
├── dashboard/     Presentation client (Streamlit/Dash)
├── data/          Immutable data zones: raw → interim → processed
├── notebooks/     Exploration and statistical methodology
├── tests/         Verification, incl. dedicated statistical validation
├── docs/          Architecture, domain, quality-system documentation
├── scripts/       Automation and operational entry points
├── configs/       Declarative process and SPC configuration
├── models/        Statistical baselines and predictive model registry
├── reports/       Generated quality deliverables
├── logs/          Runtime logs and the audit trail
├── .cursor/       AI development environment: rules, context, commands
└── .github/       CI quality gates and collaboration templates
```

## Why each directory exists

| Directory | Exists to… | Would break if removed |
|---|---|---|
| `src/` | Hold the only importable, tested, shippable code, in a src layout so tests run against the installed package | Logic scatters into notebooks and scripts; nothing is authoritative |
| `dashboard/` | Keep presentation replaceable and prevent the UI becoming a second, unverified implementation of the analytics | Chart logic couples to the UI framework and diverges from the audited engine |
| `data/` | Enforce one-directional zones with validated contracts at each boundary | Cleaning decisions become invisible; analyses stop being reproducible |
| `notebooks/` | Separate developing understanding from delivering it | Exploratory code reaches production untested |
| `tests/` | Buy different kinds of confidence, separated by kind | Statistical defects hide among passing unit tests |
| `docs/` | Make decisions and domain knowledge retrievable by humans and the agent | Every question costs code archaeology or an agent's guess |
| `scripts/` | Turn repeated manual sequences into reviewable, runnable knowledge | Operational knowledge lives in one person's memory |
| `configs/` | Let process knowledge change without a code release, with an audit trail | Every limit change becomes a deployment; auditors get no history |
| `models/` | Version baselines and models as artefacts with lineage and approval | Superseded limits vanish; past violations become unexplainable |
| `reports/` | Guarantee every published document is regenerable from source | Deliverables exist that nobody can reproduce or defend |
| `logs/` | Separate debuggable operational output from append-only audit evidence | Audit records get rotated away with DEBUG noise |
| `.cursor/` | Make conventions explicit so the agent never re-infers architecture | Token cost rises and the agent invents contradictory patterns |
| `.github/` | Automate the quality gates that reviewers cannot reliably catch by eye | A changed estimator merges unnoticed |

---

## The dependency rule

Dependencies point inward. This is the one structural rule that is never bent.

```
   dashboard ─┐
   api ───────┼──→ application ──→ domain ←── analytics
   cli ───────┘          │                        │
                         ↓                        │
                  infrastructure ─────────────────┘
                         (implements ports defined inward)
```

- `domain/` imports nothing else in this repository.
- `analytics/` imports only `domain/` and `common/` — no I/O, no frameworks.
- `application/` orchestrates via interfaces, never concrete adapters.
- `infrastructure/` is the only place third-party systems are touched.
- `dashboard/`, `api/`, and `cli/` are interchangeable front doors onto the
  same use cases.

If a needed import runs against this direction, the design is wrong, not the
rule. The usual fix is a port defined inward and implemented outward.

---

## Data flow

```
fab export / simulator
        ↓
   data/raw/ ──────────────── immutable, never edited
        ↓  (pipelines: ingest, validate against data/schemas/)
   data/interim/ ──────────── disposable, pipeline-internal only
        ↓  (normalise units, resolve re-measurements, aggregate)
   data/processed/ ────────── analysis-ready, single source of truth
        ↓
   analytics engine ← configs/spc/ (policy) + models/baselines/ (limits)
        ↓                          + data/reference/ (spec limits)
   violations, capability, MSA results
        ↓
   dashboard/ · reports/ · logs/audit/
```

Two inputs feed the engine from opposite directions, and the architecture
keeps them apart deliberately: **specification limits** come from the device
requirement (`data/reference/`, versioned, approved), while **control limits**
are derived from a qualified process baseline (`models/baselines/`, computed,
frozen, superseded on change). They are distinct types in the domain layer and
cannot be substituted for one another. Conflating them is the most common
serious error in SPC tooling.

---

## Where does this code go?

A decision guide for contributors and for the agent.

| If it… | It belongs in |
|---|---|
| Expresses a fab concept or an invariant | `src/spc_platform/domain/` |
| Computes a chart, limit, capability index, or run rule | `src/spc_platform/analytics/` |
| Coordinates a complete engineering action | `src/spc_platform/application/` |
| Reads or writes anything outside the process | `src/spc_platform/infrastructure/` |
| Moves data between zones | `src/spc_platform/pipelines/` |
| Renders something on screen | `dashboard/` |
| Is a repeated manual sequence | `scripts/` |
| Is process knowledge that changes without a release | `configs/` or `data/reference/` |
| Is a one-off investigation | `notebooks/` |
| Explains why a choice was made | `docs/adr/` |
| Is a constraint the agent must always honour | `.cursor/rules/` |

Which module owns a given capability, and which layer each of its parts belongs
in, is set out in [../MODULE_DESIGN.md](../MODULE_DESIGN.md) and the ten
specifications in [../modules/](../modules/).

---

## Conventions that apply repository-wide

- Full type annotations; `mypy --strict` is a gate.
- No module-level side effects. Importing the package opens nothing.
- Configuration is parsed once at the boundary into typed, immutable objects.
- Every statistical function names its estimator; "sigma" alone is never
  acceptable.
- Every statistic reported to a user carries its sample size and time window.
- No confidential process data, device names, or credentials in any committed
  file.
- Documentation and `.cursor/rules/` are updated in the same pull request as
  the change they describe.

---

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 1 | Repository structure and rationale | Complete |
| 2 | Project documentation | Complete |
| 3 | Product requirements | Complete |
| 4 | Cursor rules (`.cursor/rules/`) | Complete |
| 5 | Module design (`docs/MODULE_DESIGN.md`, `docs/modules/`) | Complete |
| 6 | Toolchain and CI foundation | Complete |
| 7 | Domain model and configuration | Complete |
| 8 | Synthetic fab data generator | Next |
| 9 | SPC analytics engine | Planned |
| 10 | Data pipelines and persistence | Planned |
| 11 | Application layer, API, CLI | Planned |
| 12 | Dashboard | Planned |
| 13 | Reporting, excursion workflow, audit packages | Planned |
| 14 | Deployment and operations | Planned |
| 15 | Advanced analytics | Stretch |

Deliverables and exit criteria per phase are in
[../DEVELOPMENT_ROADMAP.md](../DEVELOPMENT_ROADMAP.md); current status is in
[../PROJECT_PROGRESS.md](../PROJECT_PROGRESS.md).

Domain vocabulary and typed configuration exist; analytics and pipelines do
not yet. That sequencing is deliberate: the types that make silent numerical
errors unrepresentable landed before the first statistic is computed.
