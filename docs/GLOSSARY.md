# Glossary

**Document owner:** Project lead
**Status:** Active
**Last updated:** 2026-08-03

The authoritative vocabulary for this project. Every term defined here means
exactly this in code, configuration, documentation, and the user interface —
identifiers in `src/spc_platform/domain/` are named directly from it.

Ambiguous vocabulary is a real source of defects in manufacturing analytics.
"Sample" means one thing to a statistician and another to a metrology
technician; "lot" and "batch" are used interchangeably in conversation and must
not be in a schema. This document resolves those collisions once.

---

## 1. Manufacturing hierarchy

**Lot** — The unit of material movement through the fab. Conventionally 25
wafers in a 300 mm FOUP, though partial lots occur. Carries a unique lot ID
through its entire route. *In this project, `Lot` is the aggregation level at
which most process control decisions are made.*

**Wafer** — A single substrate. Identified by lot ID plus slot number (1–25).
Slot position is not merely an identifier: it correlates with position in the
process chamber and is a legitimate explanatory variable for systematic
variation.

**Die** — An individual device on the wafer, defined by the reticle field and
step pattern. Relevant to yield analysis; generally not the unit of parametric
process measurement.

**Site** — A defined measurement location on a wafer, specified by the
sampling plan (commonly 5, 9, 13, 17, or 49 sites). Site coordinates are
fixed and known, which is what makes spatial signature analysis possible.
*A site measurement is one data point; the set of sites on a wafer is not
automatically a rational subgroup — see* **Rational subgrouping**.

**Reticle field** — The area exposed in a single lithography exposure,
containing one or more dice.

**Route / flow** — The ordered sequence of process steps a lot passes through,
typically 400–1200 steps for a modern CMOS device.

**Process step (operation)** — A single named operation in the route, e.g.
gate oxidation, poly etch, CMP. Identified by an operation number that is
stable across product variants.

**Layer** — A logical grouping of steps building one structural level of the
device (e.g. metal 1, contact, gate).

**Tool (equipment)** — A physical processing or metrology machine, identified
by an equipment ID.

**Chamber (module)** — An independently operating process volume within a
tool. A cluster tool may hold four to six chambers. **Chambers within one tool
routinely behave as distinct processes**, and pooling them without checking is
a classic cause of inflated variance and non-signalling charts.

**Recipe** — The parameterised program executed by a tool for a given step and
product.

**Product / device / technology node** — The item being manufactured and its
process generation (e.g. 28 nm planar CMOS, 16 nm FinFET).

## 2. Measurement and metrology

**Parameter** — A measurable process characteristic: film thickness, critical
dimension, overlay, sheet resistance, particle count, etch depth. Every
parameter has a declared unit, a metrology method, and a sampling plan.

**Critical dimension (CD)** — The measured width of a patterned feature,
typically by CD-SEM or scatterometry. A primary lithography and etch control
parameter.

**Overlay** — Misalignment between the current patterned layer and the layer
beneath it, measured as a vector (x, y) in nanometres.

**Sheet resistance (Rs)** — Resistance per square of a deposited film, measured
by four-point probe; a proxy for film thickness and composition.

**WAT / PCM (Wafer Acceptance Test / Process Control Monitor)** — Electrical
measurements on test structures at the end of the line. Late-stage,
high-value, low-frequency data.

**FDC (Fault Detection and Classification)** — Analysis of high-frequency
equipment sensor traces (pressure, RF power, gas flow) during processing.
Adjacent to this platform; explicitly out of scope for now.

**Sampling plan** — The declared rule for what gets measured: which lots, which
wafers, which sites. Fabs measure a fraction of material, so the plan
determines what the SPC system can possibly detect.

**Measurement system** — The complete apparatus producing a value: tool,
recipe, operator, procedure, and environment. SPC charts the process *and* the
measurement system together, which is why the latter must be qualified first.

**MSA (Measurement System Analysis)** — Study of measurement system adequacy.
Per AIAG MSA, comprises bias, linearity, stability, repeatability, and
reproducibility.

**Gauge R&R** — Repeatability (same operator, same part, repeated) and
Reproducibility (different operators/conditions) combined. Reported as %GRR of
tolerance or of total variation. Common guidance: **< 10% acceptable, 10–30%
conditionally acceptable, > 30% unacceptable.** ANOVA method preferred over
average-and-range.

**NDC (Number of Distinct Categories)** — Resolution of the measurement system
relative to part variation; ≥ 5 is the usual requirement.

## 3. Statistical process control

**SPC** — Statistical Process Control. Using statistical methods to
distinguish common-cause from special-cause variation and to act only on the
latter.

**Common cause variation** — Inherent, random variation from the many small
influences always present. A stable process exhibits only common cause
variation. **Reacting to common cause variation is over-adjustment, and it
increases variation.**

**Special cause variation** — Variation from an identifiable, non-random
source: a tool drift, a wrong recipe, a degrading component, a material
change. This is what control charts are designed to detect.

**In control (stable)** — The process exhibits only common cause variation.
Note carefully: **in control does not mean acceptable.** A process can be
perfectly stable and consistently out of specification.

**Out of control (OOC)** — A control chart run rule has signalled, indicating
probable special cause. Requires investigation per the reaction plan.

**Out of specification (OOS)** — A measured value falls outside the
specification limits. A material disposition question, distinct from OOC.

**Excursion** — A significant, confirmed process deviation requiring
containment, investigation, and disposition of affected material.

**Control chart** — A time-ordered plot of a statistic with a centre line and
control limits, used to detect special cause variation.

**Centre line (CL)** — The expected value of the plotted statistic under
stable operation.

### Control limits versus specification limits

This distinction is foundational to the entire architecture and is enforced by
the type system in `src/spc_platform/domain/`.

**Control limits (UCL / LCL)** — Derived **from the process**, conventionally
at ±3σ of the plotted statistic, computed from a qualified baseline period.
They describe what the process *does*. They are computed, frozen, versioned,
and recalculated only through an approved procedure.

**Specification limits (USL / LSL)** — Derived **from the device requirement or
the customer**. They describe what is *acceptable*. They are reference data,
approved and versioned, never computed from process data.

> Control limits and specification limits **never appear on the same chart as
> if they were equivalent**, are never substituted for one another, and are
> distinct, non-interchangeable types in code. Placing spec limits on a control
> chart as control limits guarantees that a shift is detected only after
> material is already non-conforming.

**Rational subgrouping** — Selecting subgroups so that variation *within* a
subgroup reflects only common cause, and variation *between* subgroups reveals
special cause. **The central design decision of any control chart.**

In semiconductor work this is a trap: using the sites on a wafer as a subgroup
folds the systematic radial signature into the within-subgroup estimate,
inflating σ̂, widening control limits, and producing a chart that never
signals. The usual correct treatment is to chart the wafer mean across wafers
and to handle within-wafer signature as a separate spatial analysis.

### Chart types

**I-MR (Individuals and Moving Range)** — One measurement per time point.
Sigma estimated from the average moving range (σ̂ = MR̄ / d₂, d₂ = 1.128 for
n = 2). The default when no rational subgroup exists.

**X̄-R** — Subgroup mean and range; conventional for subgroup size 2–9.

**X̄-S** — Subgroup mean and standard deviation; preferred for subgroup size
≥ 10, where the range becomes an inefficient estimator.

**EWMA (Exponentially Weighted Moving Average)** — Weights recent observations
more heavily via a smoothing constant λ (typically 0.1–0.3). Substantially
more sensitive than a Shewhart chart to small sustained shifts (≤ 1.5σ) —
which is precisely the drift profile of a slowly degrading process tool.

**CUSUM (Cumulative Sum)** — Accumulates deviations from target. Like EWMA,
tuned for small persistent shifts; parameterised by reference value k and
decision interval h.

**Attribute charts** — For counts rather than measurements: **p** (proportion
defective, variable n), **np** (count defective, constant n), **c** (defect
count, constant opportunity), **u** (defects per unit, variable opportunity).
Used for particle and defect data.

### Run rules

**Run rules (detection rules)** — Patterns that signal probable special cause
beyond a single point outside the limits.

**Western Electric rules** — The classical set: (1) one point beyond 3σ;
(2) two of three consecutive points beyond 2σ on the same side; (3) four of
five beyond 1σ on the same side; (4) eight consecutive points on one side of
the centre line.

**Nelson rules** — An extended eight-rule set adding trend, oscillation,
stratification, and mixture patterns.

**Zones (A, B, C)** — The bands between the centre line and control limits, at
1σ, 2σ, and 3σ, used to express the rules above.

**ARL (Average Run Length)** — Expected number of points before a signal.
**ARL₀** is the in-control ARL (false-alarm behaviour); **ARL₁** is the
out-of-control ARL (detection speed). For a single 3σ rule on normal data,
ARL₀ ≈ 370. **Enabling all four Western Electric rules drops ARL₀ to roughly
90 — a fourfold increase in false alarms.** Every rule added buys sensitivity
and costs credibility, which is why rule sets are configured per parameter and
their ARL measured, not assumed.

**Alarm fatigue** — Operator desensitisation caused by excessive false alarms.
Treated in this project as a defect class, not a user-training issue.

**OCAP (Out of Control Action Plan)** — The predetermined reaction plan
specifying what to do when a specific chart signals. Required by IATF 16949
control plan practice; linked from every alarm in this platform.

**Disposition** — The recorded decision about affected material and the
process: continue, hold, rework, scrap, or use-as-is with concession.

## 4. Process capability

**Process capability** — The ability of a stable process to produce output
within specification. **Only meaningful for a process demonstrated to be in
statistical control**; a capability index computed on an unstable process
describes a distribution that does not exist.

**Cp** — Potential capability: (USL − LSL) / (6σ̂_within). Ignores centring.

**Cpk** — Actual capability: min[(USL − μ̂)/(3σ̂_within), (μ̂ − LSL)/(3σ̂_within)].
Accounts for centring. **Cp ≥ Cpk always.**

**Pp / Ppk** — Performance indices, identical in form but computed with
**overall (long-term) sigma**, the ordinary sample standard deviation of all
data.

**Cpm (Taguchi index)** — Penalises deviation from target, not merely from the
limits. Appropriate where being on target has value beyond conformance.

**Short-term sigma (σ̂_within)** — Estimated from within-subgroup variation
(R̄/d₂, s̄/c₄, or MR̄/d₂). Represents the process's inherent capability.

**Long-term sigma (σ̂_overall)** — The ordinary standard deviation of all
observations, including between-subgroup drift.

> Reporting Cpk computed with overall sigma is a silent misstatement — the
> label says short-term capability, the number describes long-term
> performance. **Every capability output in this platform states its estimator
> explicitly, alongside sample size and time window.**

**Sigma shift (1.5σ)** — The empirical long-term drift allowance conventionally
assumed in Six Sigma calculations. A convention, not a law, and always stated
when applied.

**Common capability targets** — Cpk ≥ 1.33 (4σ, typical general requirement),
Cpk ≥ 1.67 (5σ, common for automotive safety-relevant characteristics),
Ppk ≥ 1.67 often required at PPAP for new processes. Actual requirements come
from the control plan, never from a default in software.

**Non-normal capability** — Many semiconductor parameters (particle counts,
defect densities, overlay magnitude) are not normally distributed. Applying
normal-theory capability formulae to them produces meaningless indices.
Handled by transformation (Box-Cox, Johnson) or percentile methods (Clements),
with the method always recorded.

## 5. Variation structure

**Variance components** — Decomposition of total variation into its nested
sources. In wafer fabrication: **within-wafer** (site to site),
**wafer-to-wafer** (within a lot), and **lot-to-lot** (over time), plus
tool-to-tool and chamber-to-chamber terms.

This decomposition directs improvement effort. If 70% of total variance is
within-wafer, chasing lot-to-lot drift is wasted work — and a time-series
control chart alone would never reveal that.

**Within-wafer uniformity (WIW)** — Variation across a single wafer, often
expressed as range or as a percentage. Typically has a *spatial signature*
rather than being random.

**Spatial signature** — A systematic within-wafer pattern: centre-to-edge
(radial), edge-only, left-right asymmetry, or a slot-correlated pattern. Each
maps to identifiable physical causes — gas flow, temperature profile, chuck
contact, rotation. Invisible in a time-series chart; visible immediately on a
wafer map.

**Wafer map** — Spatial plot of measurements at their true site coordinates.

**Tool matching (chamber matching)** — Verifying that parallel tools or
chambers produce statistically equivalent output. A tool-to-tool offset is one
of the most frequent explanations for an apparent process shift, and one of
the most frequently missed.

**Commonality analysis** — Identifying the tool, chamber, operator, or material
lot common to a set of affected lots. The standard first step in an excursion
investigation.

## 6. Quality system

**IATF 16949** — The automotive sector quality management standard, built on
ISO 9001. Governs suppliers to the automotive industry, including
semiconductor suppliers.

**VDA 6.3** — German automotive process audit standard, widely applied by
European OEMs.

**Control plan** — The document specifying, for each characteristic, the
tolerance, the measurement method, the sample size and frequency, the control
method, and the reaction plan. **The control plan is the specification this
platform implements**; chart selection and rule configuration derive from it.

**APQP** — Advanced Product Quality Planning, the structured product/process
development framework.

**PPAP** — Production Part Approval Process. The evidence package submitted for
customer approval, typically including capability studies and MSA results.

**FMEA** — Failure Mode and Effects Analysis (AIAG-VDA harmonised format).
Risk analysis identifying failure modes and their controls; the source of many
characteristics that require SPC.

**Special characteristic** — A characteristic designated as critical or
significant to safety or regulatory compliance, carrying mandatory control and
capability requirements.

**8D** — The eight-discipline structured problem-solving report used for
customer complaints and significant internal issues.

**CAPA** — Corrective and Preventive Action.

**Traceability** — The ability to reconstruct, for any product, the full
processing and measurement history. Non-negotiable in automotive supply.

**Data integrity (ALCOA+)** — Data must be Attributable, Legible,
Contemporaneous, Original, and Accurate, plus Complete, Consistent, Enduring,
and Available. The principle behind the append-only audit trail in `logs/audit/`.

## 7. Systems and interfaces

**MES (Manufacturing Execution System)** — The system of record for lot
tracking, routing, and process history.

**YMS (Yield Management System)** — Aggregates test, defect, and parametric
data for yield analysis.

**SECS/GEM (SEMI E5 / E30 / E37)** — The standard equipment communication
protocols in semiconductor manufacturing. E5 defines message content, E30 the
generic equipment model of states, collection events, and alarms, E37 the
transport.

**EDA / Interface A (SEMI E120, E125, E132, E134, E164)** — The modern standard
for high-volume equipment data collection. E120 and E125 define the common
equipment model and equipment self-description, and are the reason the domain
model represents equipment as a tool → chamber hierarchy rather than a flat
identifier.

**Equipment state (SEMI E10)** — The standard model of how equipment time is
accounted for: **non-scheduled time**, **unscheduled downtime**, **scheduled
downtime**, **engineering time**, **standby time**, and **productive time**,
together with the availability, MTBF, and MTTR metrics derived from them.

Equipment state is context for reading a control chart, not a separate
concern. Step shifts cluster at state transitions — a return to productive time
after maintenance is the most common physical explanation for a sudden mean
shift — and a **baseline must be qualified on productive time**, since
including engineering time absorbs deliberate experimental variation into the
control limits.

**OEE / Overall Equipment Efficiency (SEMI E79)** — Equipment productivity
expressed as the product of availability, performance, and quality efficiency
components. Out of scope as a feature of this platform; the vocabulary is
aligned so that the quality-efficiency component, which this platform's output
feeds, needs no translation.

**Substrate tracking (SEMI E90)** — Standard model for wafer identity and
location through the process. The basis for treating slot position as a
first-class field rather than an array index.

**Substrate mapping (SEMI E142)** — Structured representation of per-site wafer
data. The reason site coordinates are stored as true positions in millimetres
from wafer centre rather than as an opaque site index.

**Time synchronisation (SEMI E148)** — Clock synchronisation requirements
across fab equipment. Process tools and metrology tools have independent
clocks; skew between them produces misordered series, and a run rule evaluated
over a misordered series signals on nothing real. This is why every timestamp
in the platform is timezone-aware and naive datetimes are rejected by lint
rule.

> SEMI standards are controlled publications. This project aligns with their
> vocabulary and structural models; it reproduces no standard content, uses
> none as a numerical test dependency, and claims no conformance. See
> [domain/SEMI_STANDARDS_ALIGNMENT.md](domain/SEMI_STANDARDS_ALIGNMENT.md).

**FOUP** — Front Opening Unified Pod; the sealed carrier transporting a lot.

**WIP** — Work In Progress; material currently in the production line.

**Cycle time** — Elapsed time for material to traverse the route or a segment
of it.

## 8. Project-internal terms

**Baseline** — A qualified period of stable operation used to compute control
limits, stored as a versioned artefact in `models/baselines/` with its
subgroup count, sigma estimator, approver, and effective date. Superseded
baselines are retained so that a historical violation remains explainable
against the limits actually in force at the time.

**Data zone** — One stage of the one-directional data flow: `raw` → `interim`
→ `processed`. See [DATASET_GUIDE.md](DATASET_GUIDE.md).

**Injected fault** — A deliberately introduced deviation in synthetic data
(drift, step shift, variance increase, cyclic pattern) with known ground
truth, used to score detection sensitivity and false-alarm rate.

**Violation** — A recorded instance of a run rule signalling on a specific
chart at a specific point, carrying the rule identity, severity, and
disposition state.

---

**Related:** [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) ·
[DATASET_GUIDE.md](DATASET_GUIDE.md) ·
[QUALITY_ASSURANCE_PLAN.md](QUALITY_ASSURANCE_PLAN.md) ·
[TESTING_STRATEGY.md](TESTING_STRATEGY.md)
