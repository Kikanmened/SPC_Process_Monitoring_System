# `notebooks/` — Exploration and Methodology

## Why this folder exists

Notebooks are where statistical understanding is *developed*; `src/` is where
it is *delivered*. Both are necessary, and conflating them is how analytics
projects rot: logic gets written in a cell, copied into a second notebook,
subtly modified, and eventually nobody knows which version produced the number
in the report.

The boundary here is strict and one-directional. **Notebooks import from
`spc_platform`. Nothing imports from a notebook.** A notebook is a narrative
over library code, not a place where library code lives. When a cell becomes
genuinely useful, it moves into `src/`, gains tests, and the notebook calls
the new function instead.

They also serve a portfolio purpose that source files cannot: a notebook shows
the *reasoning* — why an EWMA was chosen over an individuals chart for a given
parameter, why a transformation was needed before capability analysis. That
reasoning is exactly what a quality engineering interview probes.

## Layout

```
notebooks/
├── 00_exploration/      Open-ended investigation of process data.
├── 10_data_validation/  Data quality, distributions, missingness, outliers.
├── 20_methodology/      Justification of statistical choices.
├── 30_reporting/        Narrative analyses that back a published report.
└── templates/           Starting points enforcing a consistent structure.
```

The numeric prefixes impose reading order. A reviewer opening this folder cold
should be able to follow the analysis from raw exploration to defended
methodology to published conclusion without asking where to start.

### `10_data_validation/`
Done before any charting, always. Distribution shape, normality assessment,
missing measurements, re-measurements, sensor saturation, unit inconsistency,
timestamp integrity. A control chart built on unvalidated data is a
confident-looking wrong answer, and this folder is where that is caught.

### `20_methodology/`
The defensible core: chart type selection per parameter class, subgroup
strategy and its effect on within- versus between-subgroup variation, sigma
estimator choice, run-rule set selection with its false-alarm trade-off, and
handling of non-normal parameters. Conclusions reached here become
configuration in `configs/spc/` — the notebook is the justification, the
config is the enforcement.

## Conventions

- **Naming:** `NN_short_description.ipynb`, prefix matching the folder.
- **Structure:** every notebook opens with purpose, data source and revision,
  and the question being answered; it closes with explicit conclusions. A
  notebook that ends in an untitled plot has communicated nothing.
- **Reproducibility:** parameters in the first cell, no hard-coded absolute
  paths, data read from `data/processed/` or `data/synthetic/` only — never
  from `raw/` or `interim/`.
- **Output hygiene:** outputs are cleared before commit. Committed cell output
  produces unreadable diffs and can leak data.
- **No confidential data** in committed notebooks — use `data/synthetic/`.
- **Promotion rule:** any function used in a second notebook belongs in
  `src/spc_platform/`, with tests, before it is used again.
