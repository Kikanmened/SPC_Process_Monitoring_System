# `docs/` — Engineering and Quality Documentation

## Why this folder exists

Two audiences, one source of truth.

**For engineers:** a semiconductor SPC platform sits at the intersection of
statistics, process engineering, and software. A new contributor who knows
Python but not what a Cpk of 1.33 implies — or a process engineer who knows
exactly what it implies but not this codebase — must both be able to become
productive from this folder.

**For the AI agent:** this is the mechanism that keeps Cursor from re-deriving
the architecture on every request. An agent that can read a decision record in
two hundred tokens does not need to read four thousand lines of source to
infer the same conclusion — and, unlike the inference, the record is
authoritative. Documentation here is written to be *retrieved in fragments*,
which is why it is many focused files rather than a few long ones.

## The document set

The project-level documents live flat in this folder. The subdirectories hold
the detailed, per-topic material that accumulates as implementation proceeds.

**Start here**

| Document | Answers |
|---|---|
| [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) | What problem is this, who is it for, and what is out of scope? |
| [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) | What exactly must it do, and how will we know it does? |
| [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) | How is it built, and where does anything live? |
| [MODULE_DESIGN.md](MODULE_DESIGN.md) | Which module owns this capability, and what is its contract? |
| [GLOSSARY.md](GLOSSARY.md) | What does this term mean, precisely? |

**Building on it**

| Document | Answers |
|---|---|
| [TECH_STACK.md](TECH_STACK.md) | What are we using, and what did we reject? |
| [CODING_STANDARDS.md](CODING_STANDARDS.md) | How must code be written here? |
| [TESTING_STRATEGY.md](TESTING_STRATEGY.md) | How do we know the numbers are right? |
| [DATASET_GUIDE.md](DATASET_GUIDE.md) | What is the data model and where does data come from? |
| [DECISION_LOG.md](DECISION_LOG.md) | Why is it done this way? |
| [domain/SEMI_STANDARDS_ALIGNMENT.md](domain/SEMI_STANDARDS_ALIGNMENT.md) | Which SEMI standards shape the vocabulary and equipment model? |

**Running and governing it**

| Document | Answers |
|---|---|
| [QUALITY_ASSURANCE_PLAN.md](QUALITY_ASSURANCE_PLAN.md) | How does this fit a quality management system? |
| [DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md) | How does it reach a fab and stay running? |
| [RISK_REGISTER.md](RISK_REGISTER.md) | What could go wrong, and what are we doing about it? |

**Tracking it**

| Document | Answers |
|---|---|
| [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) | What is the plan, and what does "done" mean per phase? |
| [PROJECT_PROGRESS.md](PROJECT_PROGRESS.md) | Where are we right now? |
| [../CHANGELOG.md](../CHANGELOG.md) | What changed, and when? |
| [architecture/repository-structure.md](architecture/repository-structure.md) | Why is the repository laid out this way? |

## Layout

```
docs/
├── adr/            Architecture Decision Records. Why, not what.
├── architecture/   Structure, data flow, component boundaries.
├── modules/        One specification per module: interfaces, files, tests.
├── domain/         SPC theory and semiconductor manufacturing context.
├── quality/        Quality-system alignment: IATF 16949, MSA, control plans.
├── api/            Interface contracts.
├── runbooks/       Operational procedures for when something breaks.
├── onboarding/     Guided path for a new engineer or agent.
├── validation/     Evidence that the statistical engine is correct.
└── images/         Diagrams referenced by the documents above.
```

### `adr/`
Numbered, immutable decision records: the context, the options considered, the
choice, and the consequences. Superseded decisions are marked superseded, not
deleted — the history of *why* is worth more than a tidy current state. This
answers the question that otherwise costs an afternoon of code archaeology:
"why is it done this way?"

### `modules/`
The ten module specifications indexed by
[MODULE_DESIGN.md](MODULE_DESIGN.md). Each states purpose, responsibilities,
public interfaces, dependencies, inputs and outputs, the files it creates, its
testing and documentation obligations, and its extension points. This is the
folder to read before writing code in an unfamiliar part of the system, and the
one that answers "where does this belong?" without inference.

### `domain/`
The bridge between statistics and silicon, and the folder that makes this
project legible to a semiconductor quality organisation:

- SPC fundamentals and the reasoning behind chart selection.
- Control limits versus specification limits — the distinction the entire
  architecture is built around.
- Capability indices, with the short-term/long-term sigma question addressed
  explicitly rather than assumed.
- Western Electric and Nelson run rules, and the false-alarm cost of enabling
  all of them at once.
- Semiconductor context: lot/wafer/site hierarchy, within-wafer and
  wafer-to-wafer variance components, tool and chamber matching, metrology
  sampling plans, common process signatures and their physical causes.
- A glossary, so that "site", "lot", "excursion", "commonality", and "OCAP"
  mean one thing across code, UI, and documentation.

### `quality/`
Alignment with the quality management system a European automotive-facing fab
actually runs on: IATF 16949 and ISO 9001 expectations, control plan
structure, MSA requirements, reaction plans and OCAPs, 8D and CAPA linkage,
and audit-trail and data-integrity requirements. This folder is what separates
a charting tool from a quality system component.

### `validation/`
Evidence, not claims: reference datasets used, expected values with their
sources, and the reasoning behind each statistical acceptance criterion. It is
the written companion to `tests/statistical/`. If someone asks "how do you
know your Cpk is right?", the answer is a link into this folder.

### `runbooks/`
What to do when the ingestion job fails, when limits look wrong, when a data
source changes format, when an alarm storm fires. Written for someone under
time pressure who did not build the system.

## Conventions

- Markdown, one topic per file, headings that state conclusions.
- Every ADR is numbered and dated; ADRs are never rewritten in place.
- Formulae state their estimator and cite a source.
- Documentation lands in the same pull request as the change it describes.
  Documentation written "later" is documentation written never.
- Diagrams are text-based (Mermaid) wherever possible, so they diff and review
  like code.
