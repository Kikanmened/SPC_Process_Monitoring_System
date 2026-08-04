# `dashboard/` — Operator and Engineer Interface

## Why this folder exists — and why it is not inside `src/`

The dashboard is a **presentation client**, deliberately separated from
`src/spc_platform/` so the separation is structural rather than a matter of
discipline. Three reasons:

1. **The UI framework is the most replaceable part of the system.** Streamlit
   today, Dash or a React front end tomorrow. If chart logic lived in the UI
   layer, that swap would mean rewriting the statistics. Here it means
   rewriting only rendering.
2. **The UI must never be a second implementation of the analytics.** A
   violation shown on screen and a violation recorded in the audit log must
   come from the same call into `spc_platform`. Any computation performed
   inside a page is, by definition, an unverified duplicate of logic that is
   tested elsewhere.
3. **It has different quality requirements.** UI code is validated by
   interaction tests and visual review; the statistical core is validated by
   numerical proof. Different rigour, different lifecycle, different folder.

## Layout

```
dashboard/
├── app/          Entry point, routing, session bootstrap.
├── pages/        One file per screen.
├── components/   Reusable widgets (chart panel, violation badge, filters).
├── layouts/      Page scaffolding and grid structure.
├── state/        Session state, filter selections, caching policy.
├── assets/       Static files: logos, icons, CSS.
├── theme/        Colour tokens, typography, chart styling.
└── tests/        UI-level tests.
```

## Intended screens

The page set follows how a fab engineer actually works, not how the data
happens to be stored:

- **Line overview** — health across areas and tools, ordered by what needs
  attention now, not alphabetically.
- **Control chart viewer** — the core screen. Chart with limits and violation
  markers, subgroup detail on selection, and an annotation trail.
- **Capability analysis** — Cp/Cpk/Pp/Ppk with the distribution, the spec
  limits, and an explicit statement of which sigma estimator was used.
- **Wafer map** — spatial signature view; centre-to-edge and radial patterns
  are invisible in a time-series chart and are often the actual root cause.
  Interactive Plotly with full site drill-down — see below.
- **Tool and chamber comparison** — matched-parameter comparison to expose
  tool-to-tool offsets, the most common source of an apparent process shift.
- **Alarm and disposition queue** — open out-of-control events with
  acknowledgement, root-cause note, and disposition, forming the audit trail.
- **Gauge R&R / MSA** — measurement system health, because every other screen
  is only as trustworthy as the gauge behind it.

## Design principles

- **Answer the operator's question in one screen.** The question is almost
  always "is this normal, and if not, what do I do?" A chart that requires
  three clicks to reveal whether a point violated a rule has failed.
- **Distinguish spec limits from control limits visually and always.** They
  are different concepts, drawn differently, never on the same axis style.
  Conflating them in a UI teaches the wrong mental model to every user.
- **Show sample size and time window on every statistic.** A Cpk with no
  stated n and no window is a number without meaning.
- **Never invent a number.** If the backend cannot compute a value, the UI
  says so. It does not interpolate, fall back to a default, or hide the gap.
- **Colour carries meaning, and never alone.** Out-of-control state is marked
  by shape and label as well as colour; a meaningful fraction of process
  engineers are colour-vision deficient, and a red-only signal is invisible
  to them.

## Wafer map rendering

Settled by ADR-0018. Interactive Plotly is the primary visualisation; static
images exist only as export artefacts.

**The pipeline, and where each stage lives:**

```
repository query          infrastructure/
  → signature detection   analytics/spatial/
  → view assembly         application/  (GetWaferMap → WaferMapView)
  → figure construction   dashboard/components/wafer_map.py
  → caching + filters     dashboard/state/
  → static export         reports/  (Matplotlib, same WaferMapView)
```

`WaferMapView` is the seam. The interactive figure and the static export
consume the identical value object, so a wafer map in a PDF report and one on
screen cannot disagree — two renderings of one computation, not two
computations.

**Requirements**

- Individual site markers at true coordinates (mm from wafer centre)
- Hover metadata: lot, wafer, slot, site, coordinates, value, unit, deviation
  from target
- Wafer boundary, notch/flat orientation, and exclusion zone drawn explicitly
- Deviation and defect heatmaps, including binned/contour representation
- Filtering by lot, wafer, tool, chamber, parameter, and time window

**Two rules that exist because breaking them fabricates a signature**

These are correctness constraints, not styling preferences. The wafer map is a
*detection surface*, and a rendering that invents or conceals a pattern
produces a wrong engineering conclusion — while being far less likely to be
questioned than a wrong number, because it is "just a chart".

1. **Colour scale limits are fixed across any comparison set** and shown
   numerically. Per-wafer autoscaling makes a wafer varying by 0.2 nm look
   identical to one varying by 20 nm, destroying the comparison the screen
   exists to support. Autoscaling is available only as an explicit, labelled
   user action.
2. **Perceptually uniform, colour-vision-safe scales only** — sequential
   (viridis, cividis) for values, diverging centred on target for deviation.
   Rainbow and jet scales introduce sharp perceived boundaries across smooth
   data, manufacturing an apparent edge ring or radial band that is not there.

**Scale guardrail.** One wafer is at most 49 sites and a lot around 1 200
points — both trivial. The risk is an unfiltered query spanning months. Cap
individually rendered markers at ~5 000 per figure; above that, degrade to an
aggregated view **and say so on screen**. Reject a wafer map query carrying no
lot, wafer, or time filter rather than attempting it.

**Cache invalidation.** Cache keys include the data revision and the
configuration revision. A screen serving a cached map built from superseded
data is a correctness bug, not a performance detail.

## Rules

- No statistics in this folder. Call `spc_platform`.
- No direct database or file access. Go through the application layer.
- Data loads through an explicit caching policy; a screen that silently serves
  stale limits after a baseline recalculation is a correctness bug, not a
  performance detail.
