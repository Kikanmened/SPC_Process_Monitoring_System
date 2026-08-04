# `.github/` — Collaboration and Continuous Integration

## Why this folder exists

In a quality-critical system, the pipeline defined here *is* the quality gate.
A statistical engine cannot rely on reviewers noticing that a sigma estimator
changed — the check must be automated, mandatory, and impossible to skip.

It also serves a second purpose specific to this project: a green pipeline
badge and a readable workflow file are, for anyone evaluating this repository,
direct evidence of how the author works. The CI configuration is part of the
portfolio, not scaffolding around it.

## Layout

```
.github/
├── workflows/       CI/CD pipeline definitions.
├── actions/         Composite actions shared across workflows.
├── ISSUE_TEMPLATE/  Structured intake for defects and process changes.
└── PULL_REQUEST_TEMPLATE.md
```

## Pipeline stages

`workflows/ci.yml`, ordered fastest-failing first so a formatting error never
consumes a full test run. Each job runs `scripts/ci/gate.sh <gate>` and nothing
else, which is what makes a green `make check` mean the same thing as a green
pipeline.

| Job | Gate | What it proves |
|---|---|---|
| Format, lint, types, architecture | G1–G3 | Ruff, `mypy --strict`, `import-linter`, internal documentation links |
| Unit tier | G4 | The fast bulk of the suite |
| **Statistical validation** | G5 | Control limits, capability indices, and rule detection against cited reference values |
| Contract tier | G6 | Ports and boundaries still compatible |
| Integration tier | G7 | Adapters against real dependencies |
| End-to-end tier | G8 | One full path per critical journey |
| Performance budgets | G9 | The budgets in SYSTEM_ARCHITECTURE.md §7 |
| Security | G10 | `bandit`, `pip-audit` against the lockfile, `gitleaks` over working tree and history |
| Coverage non-regression | G11 | `domain/` and `analytics/` never lose coverage they had |
| All gates | — | One required check, so adding a job cannot leave a gate unrequired |

**Statistical validation is its own job deliberately.** A failure there means a
number the platform produces is wrong, and that must be unmistakable in the run
summary rather than buried among hundreds of passing unit tests.

`workflows/nightly.yml` runs the same gates on a schedule, because a dependency
that was clean at merge may not be clean next month, and the performance tier
gets a full run where timing is less contended.

## Issue templates

Structured to capture what is actually needed to act:

- **Incorrect statistical result** — severity S1 by definition. Requires the
  produced value, the expected value *with its source*, the data, code, and
  configuration revisions, and the known exposure. A wrong number obliges an
  assessment of every result produced since it was introduced, and that
  assessment is only possible from the provenance recorded here.
- **Defect report** — what happened, what was specified, the evidence, the
  severity, the affected requirement, and the acceptance criteria.
- **Capability proposal** — for anything the platform does not currently
  promise, including the proposals recorded in `docs/MODULE_DESIGN.md` §5.
  Requires the engineering need, the owning module, the statistical basis, and
  an explicit check against the recorded non-goals.

## Pull request template

Prompts for the things that are expensive to discover after merge: what
changed and why, which statistical behaviour is affected, which tests prove
it, whether documentation and `.cursor/rules/` were updated, and whether any
existing baseline or report is invalidated by the change.

## Conventions

- Branch protection on `main`, requiring the **All gates** check.
- Conventional commit messages, enforced by a `commit-msg` hook
  (`scripts/ci/check_commit_message.py`), so history is machine-readable and
  the `stat:` marker makes every change to statistical behaviour findable.
- Actions are pinned to a commit SHA with the version in a trailing comment. A
  floating tag is a dependency that can be rewritten under you.
- Secrets come from the repository secret store. Never from a file, never from
  a log line.
- Workflow logic lives in `scripts/ci/` so it can be run locally. YAML is
  orchestration, not implementation.
