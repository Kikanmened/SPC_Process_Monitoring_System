# `configs/` — Declarative Configuration

## Why this folder exists

In a fab, process knowledge changes far more often than code. A new tool is
qualified, a control limit is recalculated after a chamber rebuild, an
engineer tightens a run-rule set on a drift-prone parameter. If that knowledge
is embedded in Python, every process change becomes a code change, a release,
and a deployment — and the people who actually own the decision cannot make it.

So process knowledge is **declarative, versioned, reviewable, and validated**.
A quality engineer can read `configs/spc/` and understand exactly how the
system will behave, without reading a line of Python. Because it is in git,
every change carries an author, a timestamp, a reviewer, and a reason — which
is precisely what an IATF 16949 audit asks for.

## Layout

```
configs/
├── base/           Defaults shared by every environment.
├── environments/   Per-environment overlays (local, dev, staging, prod).
├── spc/            Chart types, run rules, limit policy, capability settings.
├── process/        Tool, chamber, recipe, step, and parameter registry.
├── logging/        Log levels, formats, sinks, audit configuration.
├── alerting/       Routing, severity, escalation, throttling.
└── secrets/        Templates only. Real values never land here.
```

### `base/` and `environments/`
A layered model: `base/` holds defaults, an environment overlay changes only
what genuinely differs. Overlays stay small on purpose — a staging file that
redefines everything is a second configuration, and it will drift from
production and hide bugs until they surface where they cost the most.

### `spc/`
The statistical policy of the platform, expressed as data:

- Which chart type applies to which parameter class. Individuals-and-moving-
  range for a single measurement per lot; X̄-R for subgrouped site data;
  EWMA or CUSUM where small sustained shifts matter more than large spikes;
  attribute charts for defect counts.
- Which run-rule set is active where. Western Electric rules 1–4 by default,
  the full Nelson set where warranted — but never all rules everywhere, since
  each additional rule raises the false-alarm rate and an operator who learns
  to dismiss alarms is worse than no alarm at all.
- Baseline and limit policy: how many subgroups establish a baseline, when
  limits are frozen, what triggers recalculation, and who approves it.
- Capability settings: which sigma estimator, minimum sample size before an
  index is reported at all, and the handling of non-normal parameters.

**Control limits are computed from a qualified baseline, not typed into a
config file.** This folder configures the *policy* that derives them. Spec
limits, which come from the device requirement, live in `data/reference/` —
a separation the codebase enforces at the type level.

### `process/`
The fab model: process steps, tools and their chambers, recipes, and measured
parameters with their units and metrology methods. Keeping this declarative
means adding a newly qualified tool is a reviewed data change, not a code
change.

### `logging/` and `alerting/`
Observability and notification behaviour, including escalation paths and
throttling. Alarm storms are a real operational hazard: a chamber excursion
that trips forty parameters simultaneously must produce one actionable
notification, not forty pages.

### `secrets/`
Templates and examples only (`*.example.yaml`). Real credentials come from the
environment or a secret manager, never from a file in this repository. The
directory exists to document *what* must be supplied, and the root
`.gitignore` blocks everything else in it.

## Conventions

- YAML, with a schema. Every config file is validated on load by a typed
  settings model in `src/spc_platform/config/`; an unknown key is an error,
  not a silently ignored typo.
- Configuration is parsed once at the application boundary. No module reads
  YAML or environment variables at import time.
- No secrets, no absolute local paths, no machine-specific values.
- Any change to a control limit policy or a spec-limit reference is a
  reviewed pull request, and the reason belongs in the commit message.
