# `.cursor/` — AI Development Environment

## Why this folder exists

This is the difference between using an AI assistant and *engineering* with
one. Without it, every session begins with the agent rediscovering the
architecture by reading source files, re-deriving conventions it cannot see,
and occasionally inventing a plausible-looking pattern that contradicts the
one already in use. That is expensive in tokens, slow, and — worst — silently
inconsistent.

This folder makes the project's knowledge **explicit, retrievable, and
enforceable**, so the agent starts every task already knowing the layering
rules, the domain vocabulary, and the non-negotiable constraints. It is
committed to version control because it is shared engineering infrastructure,
exactly like the CI configuration.

The economics are concrete. Inferring a convention costs thousands of tokens
of file reading and produces a guess. Reading a rule costs a few hundred and
produces the answer.

## Layout

```
.cursor/
├── rules/      Persistent behavioural rules (.mdc), scoped by path.
├── commands/   Reusable slash commands for repeated workflows.
├── skills/     Deeper procedural knowledge invoked on demand.
├── context/    Curated architecture and domain summaries for retrieval.
└── prompts/    Reference prompt patterns for recurring task types.
```

### `rules/`
The core mechanism. Rules are scoped so an agent editing `src/analytics/`
receives the statistical-rigour constraints, one editing `dashboard/` receives
the presentation-layer constraints, and neither pays the token cost of the
other.

| Rule | Single responsibility | Scope |
|---|---|---|
| `project-core.mdc` | Source-of-truth routing and universal safety constraints | Always applied; lightweight |
| `product-manager.mdc` | Product intent and requirement traceability | Product planning and change records |
| `semiconductor-quality-engineer.mdc` | Semiconductor and quality-system correctness | Domain, analytics, application, process config, and quality docs |
| `senior-python-architect.mdc` | Python architecture and design quality | Python source, dashboard, and scripts |
| `testing-engineer.mdc` | Test design and verification evidence | Python tests |
| `github-maintainer.mdc` | Repository workflow and GitHub hygiene | GitHub metadata, ignore policy, ownership, and changelog |
| `documentation-writer.mdc` | Engineering documentation quality | Markdown |

`project-core.mdc` is the only global rule. It is deliberately small and routes
the agent to authoritative documents without repeating their contents. The six
specialist rules are path-scoped (`alwaysApply: false`). Several may apply to
the same file when responsibilities genuinely overlap; for example, the PRD
loads both product-management and documentation-writing guidance.

### `context/`
Compact, retrieval-shaped summaries: the module map, the data flow, the domain
glossary, the current state of the build. Written so a fragment answers a
question completely — the agent should be able to resolve "where does chart
computation live?" without opening a single source file.

### `commands/`
Encoded repeated workflows: add a control chart type, add a pipeline stage,
generate a capability report, run the statistical validation suite. A workflow
that is written down is executed the same way every time, by every contributor
and every agent.

### `skills/`
Procedural knowledge too detailed for an always-on rule and too important to
leave to inference — SPC methodology selection, MSA procedure, the release and
validation checklist. Loaded only when the task calls for it.

## Maintenance rules

- **Rules are updated in the same pull request as the change they describe.**
  A stale rule is worse than no rule: it is confidently wrong, and it will be
  followed.
- Rules state constraints and rationale, not tutorials. The agent does not
  need to be taught Python.
- Scope narrowly by path. A rule that applies everywhere is loaded everywhere
  and pays its cost on every request.
- When the agent repeatedly makes the same mistake, that is a missing rule,
  not a failing of the model. Fix it here, once.
