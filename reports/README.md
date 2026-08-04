# `reports/` — Generated Output

## Why this folder exists

Quality work produces documents, and those documents leave the building: a
weekly SPC summary for the process team, a capability study attached to a PPAP
submission, an MSA report for a qualified gauge, an excursion summary inside
an 8D. These are deliverables with consequences, and they need the same
discipline as code.

The folder enforces one rule above all: **templates are source, reports are
build output.** Every published document must be regenerable from a template
plus a data revision plus a code revision. A report that exists only as a PDF
someone produced by hand is a report nobody can reproduce, correct, or defend
when an auditor asks how the number was obtained.

## Layout

```
reports/
├── templates/        Source. Committed and reviewed.
├── generated/        Rendered output. Reproducible, git-ignored.
├── figures/          Generated charts and plots.
├── exports/          Machine-readable extracts for other systems.
└── audit_packages/   Bundled evidence for a specific audit or investigation.
```

### `templates/`
The committed source: report layouts, standard chart configurations, and the
fixed sections a quality document must contain. Changing a template is a
reviewed change, because it alters every document produced afterwards.

### `generated/`
Rendered reports, each carrying its provenance header — data revision, code
revision, generation timestamp, and the parameter set used. Without that
header, two copies of "the September capability report" cannot be told apart,
and one of them is wrong.

### `figures/`
Generated charts and plots destined for a report. Wafer maps here are **static
renders of the same `WaferMapView` the dashboard renders interactively**
(ADR-0018), produced with Matplotlib for deterministic output. Static rendering
lives here and nowhere else: on screen the interactive figure is primary,
because a static image cannot answer "which wafer, and what was the value?" —
the question that follows within seconds of noticing a pattern. Because both
consume one value object, a wafer map in a PDF and one on screen cannot
disagree.

### `exports/`
Structured extracts (CSV, Parquet, JSON) for downstream consumers: a YMS, a
supplier portal, a customer quality report. Governed by the contract tests in
`tests/contract/`, because a downstream system breaks silently when a column
is renamed.

### `audit_packages/`
A self-contained bundle assembled for a specific question: the charts, the
underlying data extract, the limits in force at the time, the configuration
revision, and the disposition records. Built so the recipient can verify the
conclusion independently rather than take it on trust — which is exactly what
an IATF 16949 or customer audit requires.

## Conventions

- Every generated artefact records its data revision, code revision, and
  generation time. No exceptions.
- Statistics are always accompanied by sample size and time window.
- Capability indices state their sigma estimator explicitly.
- Nothing in `generated/`, `figures/`, `exports/`, or `audit_packages/` is
  committed; all of it is reproducible by a command in `scripts/`.
- If a report cannot be regenerated, that is a defect in the pipeline, not a
  reason to commit the artefact.
