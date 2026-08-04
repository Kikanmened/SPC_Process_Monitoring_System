# `models/` — Statistical Baselines and Predictive Models

## Why this folder exists

"Model" here covers two distinct things, and separating them from code is what
makes both auditable.

**1. Statistical baselines — the primary use.**
A control chart's limits come from a *baseline*: a qualified period of stable
operation, with its subgroup count, its sigma estimate, the engineer who
approved it, and the date it was frozen. That baseline is a versioned artefact
with a lifecycle, not a number in a config file. When a chamber is rebuilt, the
baseline is recalculated and the old one is retained — because a violation
raised last month must be re-explainable against the limits that were actually
in force at the time. Discarding a superseded baseline destroys the audit
trail.

**2. Predictive models — the extension.**
Drift forecasting, anomaly detection beyond rule-based SPC, virtual metrology,
and excursion classification. These are genuinely useful in a fab, and they are
also where analytics platforms most often lose discipline. Keeping them here,
under the same manifest-and-card requirements as baselines, prevents an
unversioned pickle file from quietly becoming production-critical.

## Layout

```
models/
├── registry/     Manifests: what exists, its version, lineage, and status.
├── artifacts/    Serialised binaries. Output, never source.
├── experiments/  Training and tuning runs with their parameters.
├── evaluation/   Performance reports against held-out data.
├── cards/        Model cards: intent, assumptions, limits, failure modes.
└── baselines/    Frozen SPC baseline artefacts with approval metadata.
```

### `registry/`
The index of record. Each entry states what the model or baseline is, the data
revision and code revision it was produced from, when it was created, who
approved it, its lifecycle status (candidate / active / superseded / retired),
and what it supersedes. **Manifests are committed; binaries are not.** A model
must be reproducible from its manifest plus the pipeline that built it — if it
is not, the binary is the only copy of knowledge that nobody can verify.

### `cards/`
A short document per model answering the questions that determine whether it
should be trusted in a production decision: what it predicts, on what
population, under what assumptions, how it degrades, and — most importantly —
when it must **not** be used. In a manufacturing setting, a drift predictor
silently applied to a tool it was never trained on will produce confident
nonsense, and the model card is the control against that.

### `evaluation/`
Held-out performance, and for SPC detection work the metrics that actually
matter operationally: detection sensitivity against known injected faults from
`data/synthetic/`, average run length in control versus out of control, and
false-alarm rate. A detector with excellent accuracy and an intolerable
false-alarm rate is not deployable, and aggregate accuracy hides that.

## Rules

- Every artefact is immutable once registered. Improvements create a new
  version; they never overwrite an existing one.
- No model reaches active status without a card and an evaluation report.
- A superseded baseline is retained, never deleted.
- Binaries, experiment output, and frozen baselines are git-ignored; manifests,
  cards, and evaluation reports are committed.
- Rule-based SPC remains the primary detection mechanism. Predictive models
  augment engineering judgement; they do not replace a control chart that a
  process engineer can read, explain, and defend in an audit.
