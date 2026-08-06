# Technology Stack

**Document owner:** Project lead
**Status:** Active — installed; runtime dependencies in use from Phase 7
**Last updated:** 2026-08-06

Every entry states what was chosen, what it replaces, and why. A stack
document that lists tools without recording the alternatives rejected is a
manifest, not a decision record — and six months later nobody can tell whether
a choice was reasoned or accidental.

Selection criteria throughout, in priority order:

1. **Numerical trustworthiness** — mature, widely validated implementations
   for anything that touches a statistical result.
2. **Works offline** — no runtime dependency on an external service, per the
   on-premises constraint in [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md).
3. **Longevity** — a fab tool outlives fashion cycles. Boring, maintained, and
   widely known beats novel.
4. **Reviewability** — a quality engineer who is not a software specialist
   should be able to follow the code.

---

## 1. Language and runtime

| Item | Choice | Rationale |
|---|---|---|
| Language | **Python 3.13**, pinned exactly | The scientific and statistical ecosystem is unmatched, and it is the lingua franca of process engineering. Alternatives (R for statistics, Julia for performance) lose on integration and on the number of engineers who can maintain the result. |
| Typing | Full annotations, `mypy --strict` | In a numerical codebase a type error is usually a unit error in disguise. Strict mode from the first line; retrofitting types is far more expensive. |

**Version policy:** `requires-python = ">=3.13,<3.14"`. One interpreter version
is developed against, tested against, and deployed — not a range. The
interpreter is baked into the container image, so the deployed artefact runs
exactly the version CI validated, and a portability floor would buy nothing.
Testing on a version that is never deployed produces signal about a
configuration that does not exist.

`uv` manages the toolchain, so the interpreter present on a developer's machine
is irrelevant; `uv sync` installs and pins 3.13 regardless.

Python 3.14 is not adopted. The numerical stack's validation history on 3.13 is
longer, and the C-extension ecosystem is still absorbing the free-threading
work. Adoption is a scheduled revalidation exercise with its own decision
record, not a routine upgrade — see
[ADR-0016](DECISION_LOG.md#adr-0016).

## 2. Environment and packaging

| Item | Choice | Considered | Rationale |
|---|---|---|---|
| Package manager | **uv** | Poetry, PDM, pip-tools, conda | 10–100× faster resolution and install, a universal lockfile, and it manages the Python toolchain itself — so a contributor needs one tool, not three. Conda is the traditional scientific choice and was rejected: slow, heavier, and unnecessary now that the numerical wheels are reliable on PyPI. |
| Layout | **src layout**, `pyproject.toml` (PEP 621) | Flat layout | Tests run against the installed distribution, so CI validates what deploys. See [DECISION_LOG.md](DECISION_LOG.md) ADR-0001. |
| Lockfile | `uv.lock`, committed | — | Byte-reproducible environments. Mandatory for an auditable analysis; "it worked on my machine" is not a defence in a quality context. |

## 3. Numerical and statistical core

This is the part of the stack where "boring and widely validated" is a
requirement rather than a preference. Every library here has been checked
against reference implementations by a very large user base for a very long
time, which is exactly the property needed under a control chart.

| Library | Role | Notes |
|---|---|---|
| **NumPy** | Array computation | The substrate for all vectorised chart and rule evaluation. |
| **SciPy** | Distributions, statistical tests, optimisation | Normality tests, Box-Cox, percentile methods for non-normal capability. |
| **statsmodels** | ANOVA, variance components, regression | Backs Gauge R&R by the ANOVA method and nested variance decomposition. |
| **pandas** | Tabular data handling | Chosen over Polars for ecosystem depth and reviewer familiarity, not for speed. Confined to pipelines and adapters — **the analytics layer takes arrays, not DataFrames**, so a future migration touches no statistical code. |
| **PyArrow** | Parquet and columnar I/O | The storage format boundary. |

Deliberately **not** used: any SPC-specific third-party package. The control
chart mathematics is the substance of this project; delegating it to a library
would remove the thing being demonstrated, and none of the available options
carry validation evidence adequate for the claims made here. Implemented
in-house, verified against NIST/SEMATECH and Montgomery reference values in
`tests/statistical/`.

## 4. Data validation and contracts

| Item | Choice | Considered | Rationale |
|---|---|---|---|
| DataFrame schemas | **Pandera** | Great Expectations, Cerberus | Declarative column, dtype, range, and nullability contracts enforced at every data zone boundary. Great Expectations is more capable and considerably heavier than this project needs. |
| Object validation | **Pydantic v2** | attrs, dataclasses | Typed configuration, API models, and domain value objects with validation at construction. Rust core makes it fast enough to validate on every object. |
| Settings | **pydantic-settings** + YAML | Dynaconf, OmegaConf, Hydra | Layered config (`base/` plus environment overlay) parsed once into immutable typed objects. Hydra's composition power is not worth its indirection here. |

Validation is a **hard stop**. An unknown configuration key is an error, not a
silently ignored typo; a schema violation quarantines the batch and fails the
run.

## 5. Storage

| Layer | Choice | Considered | Rationale |
|---|---|---|---|
| Analytical / local | **DuckDB** | SQLite, pandas-only | Columnar, embedded, reads Parquet directly, no server. Makes the "clone and see charts in minutes" requirement achievable. SQLite is row-oriented and poor at analytical scans. |
| Production | **PostgreSQL 16 + TimescaleDB** | InfluxDB, ClickHouse, plain PostgreSQL | Measurement data is time-series with heavy relational context (lot, tool, chamber, recipe, route). Pure time-series databases handle the first well and the second badly. TimescaleDB adds partitioning, compression, and retention to a relational engine that fabs already run. |
| File format | **Parquet** | CSV, HDF5, Feather | Columnar, compressed, typed, with schema embedded. CSV is retained only at the `raw/` boundary, because that is what fab exports actually look like. |
| Access | **SQLAlchemy 2.0 Core** | Raw SQL, ORM, SQLModel | Typed query construction and dialect portability between DuckDB and PostgreSQL. Core rather than ORM: the domain model is already explicit and does not want a second mapping layer. |
| Migrations | **Alembic** | Hand-written SQL | Versioned, reversible schema changes with an audit history. |

## 6. Application interfaces

| Layer | Choice | Considered | Rationale |
|---|---|---|---|
| Dashboard | **Streamlit** | Dash, Panel, React + FastAPI | Fastest path from analysis to a usable engineering interface, in a language process engineers can read and extend. The cost — less layout control, session-state constraints — is acceptable for an internal tool and is contained behind the `dashboard/` boundary. Dash offers finer control at meaningfully higher build cost; a React front end is unjustifiable for this audience. |
| Charting | **Plotly** | Matplotlib, Altair, Bokeh | Interactive zoom, pan, and hover are essential on a control chart — an engineer must be able to inspect an individual point and reach its lot and wafer. Matplotlib is retained for static report figures, where deterministic rendering matters more than interaction. |
| API | **FastAPI** | Flask, Django REST | Pydantic-native, async-capable, generates an OpenAPI contract automatically — which is what `tests/contract/` validates against. |
| HTTP test client | **httpx2** | httpx 0.x | Required by Starlette's `TestClient` on the pinned FastAPI/Starlette stack; contract and e2e API tests use it. |
| CLI | **Typer** | argparse, Click | Type-hint driven, so the CLI signature and the function signature cannot drift apart. |
| Reports | **Jinja2 + WeasyPrint** | Quarto, ReportLab, LaTeX | HTML templates that render deterministically to PDF, with figures from Matplotlib. Reviewable in a browser during development; identical output in a report. |

## 7. Quality tooling

The gate, not the suggestion. Every item runs in pre-commit and again in CI.

| Purpose | Tool | Configuration |
|---|---|---|
| Lint + format | **Ruff** | Replaces Black, isort, Flake8, pyupgrade, and most plugins in one fast binary |
| Type checking | **mypy** | `--strict`; no untyped definitions, no implicit `Any` |
| Testing | **pytest** | With `pytest-cov`, `pytest-xdist` for parallelism |
| Property-based testing | **Hypothesis** | Generates series to verify scale- and shift-equivariance of estimators |
| Performance | **pytest-benchmark** | Asserts the budgets in [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §7 |
| Architecture enforcement | **import-linter** | Enforces the inward-only dependency rule mechanically |
| Security | **bandit**, **pip-audit**, **gitleaks** | Code patterns, dependency CVEs, and committed-secret detection |
| Docstring style | **Ruff pydocstyle (NumPy convention)** | Standard in scientific Python; supports the parameters/returns/references structure that statistical functions require |
| Notebook hygiene | **nbstripout** | Clears output before commit; prevents unreadable diffs and data leakage |
| Pre-commit | **pre-commit** | Same checks locally as in CI; a gate reachable only by pushing is too slow to be used |

## 8. Operations

| Purpose | Choice | Considered | Rationale |
|---|---|---|---|
| Logging | **structlog** | stdlib logging, loguru | Structured JSON to files, human-readable to console. Correlation IDs across pipeline, application, and API. |
| Scheduling | **APScheduler**, then cron/systemd | Airflow, Dagster, Prefect | The DAG is shallow: ingest, evaluate, report. A full orchestrator is disproportionate. Dagster is the intended upgrade path if dependencies become genuinely complex — recorded so the choice is revisited deliberately rather than defaulted into. |
| Containers | **Docker**, multi-stage | — | Reproducible deployment into a network-restricted fab environment. |
| Composition | **Docker Compose** | Kubernetes | Correct for a single-host on-prem deployment. Kubernetes is documented as an option in [DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md) but is not the base case. |
| CI/CD | **GitHub Actions** | GitLab CI, Jenkins | Native to where the code lives. Logic sits in `scripts/ci/` so it runs locally and a provider change is configuration. |
| Documentation site | **MkDocs Material** | Sphinx, Docusaurus | Renders this Markdown set directly, with search. Sphinx is stronger for API autodoc and heavier for narrative documentation, which dominates here. |
| Diagrams | **Mermaid** | draw.io, PlantUML | Text-based, so diagrams diff and review like code and cannot drift silently from the design. |

## 9. Dependency policy

- **Pin everything.** `uv.lock` is committed; production installs are
  `--frozen`. A capability study that cannot be reproduced because a transitive
  dependency moved is not evidence.
- **Justify every direct dependency.** Each addition names the problem it
  solves and the alternative rejected, in the pull request. Dependencies are
  permanent liabilities: supply chain, licence, and maintenance.
- **Licences** must be permissive (MIT, BSD, Apache-2.0). Copyleft is excluded
  to keep deployment options open, and licence compatibility is checked in CI.
- **Domain layer stays near-dependency-free.** `domain/` uses the standard
  library plus Pydantic. `analytics/` adds NumPy, SciPy, and statsmodels and
  nothing else. Dependency creep into the core is refused on principle,
  because those layers must remain trivially testable and long-lived.
- **Security scanning** runs on every pull request and on a weekly schedule,
  since a dependency that was clean at merge may not be clean next month.

## 10. Rejected, with reasons

Recorded so these are not silently reconsidered without new information.

| Rejected | Reason |
|---|---|
| **Conda / mamba** | The traditional scientific choice, now unnecessary: PyPI wheels for the numerical stack are reliable, and uv is dramatically faster. |
| **Polars instead of pandas** | Genuinely better on performance and API design, but the analytics layer takes arrays rather than DataFrames, so the benefit accrues only in pipelines while the ecosystem and familiarity costs are immediate. Revisit if ingestion becomes the bottleneck. |
| **An existing SPC library** | Removes the substance of the project, and none carries validation evidence sufficient for the claims made here. |
| **R or Julia** | Stronger in parts of the statistics; weaker in integration, deployment, and maintainer availability. |
| **Microservices** | Network boundaries between components sharing a transaction and a release cycle add failure modes and buy nothing at this scale. |
| **Kafka / streaming** | No use case currently requires sub-minute latency. Batch meets the requirement, at a fraction of the operational cost. |
| **Cloud-managed services** | Excluded by the on-premises constraint. Fabs do not export process data. |
| **Jupyter as a delivery mechanism** | Notebooks develop understanding; they do not deliver it. See `notebooks/README.md`. |

---

**Related:** [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) ·
[DECISION_LOG.md](DECISION_LOG.md) ·
[CODING_STANDARDS.md](CODING_STANDARDS.md) ·
[DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md)
