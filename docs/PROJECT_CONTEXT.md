# Project Context

**Document owner:** Project lead
**Status:** Active
**Last updated:** 2026-08-03

This document explains *why* this project exists, who it is for, and what
"done" means. It is the first document a new contributor — human or AI agent —
should read, because every architectural decision downstream traces back to
something stated here.

---

## 1. The problem

A semiconductor wafer fab measures thousands of process parameters
continuously. A single 300 mm lot carries 25 wafers; each wafer is measured at
5 to 49 sites depending on the sampling plan; each measurement belongs to one
of hundreds of process steps, each running on one of several qualified tools,
each of which may have multiple chambers. A mid-volume fab therefore generates
millions of measurement records per day.

The question asked of that data is deceptively simple:

> **Is this process behaving as it should — and if not, what changed?**

Answering it badly is expensive in both directions. A missed excursion means
defective material continues through a process flow that may take eight weeks
and hundreds of steps to complete; by the time electrical test catches it, tens
of thousands of euros of work-in-progress are affected, and in an automotive
context the escape may reach a customer. A false alarm is not free either: it
stops a healthy tool, consumes engineering time, and — most damaging — teaches
operators to dismiss alarms. A system that cries wolf is worse than no system,
because it destroys the trust that makes the real alarm actionable.

Statistical Process Control is the discipline that answers the question
properly. It is not new — Shewhart published in 1931 — but applying it
correctly to semiconductor manufacturing is genuinely difficult, and most
tooling gets parts of it wrong.

## 2. Why existing approaches fall short

The failure modes this project is built to avoid, all observed in real fab
analytics tooling:

**Conflating specification limits with control limits.** Specification limits
come from the device requirement and say what the customer will accept.
Control limits come from the process itself and say what the process normally
does. A chart drawn with spec limits as control limits cannot detect a shift
until material is already out of specification — which is precisely too late.
This is the single most common and most consequential error in SPC tooling.

**Ignoring the variance structure.** Semiconductor measurements are nested:
sites within a wafer, wafers within a lot, lots over time. Treating the five
sites on a wafer as a rational subgroup folds the systematic within-wafer
radial signature into the estimate of common-cause variation. The control
limits come out far too wide, the chart never signals, and everyone concludes
SPC "doesn't work here."

**Reporting capability without qualification.** A Cpk quoted without its sample
size, its time window, its sigma estimator, and evidence that the process was
in control when the data was collected is not a capability index. It is a
number with a Greek letter attached.

**Trusting unqualified metrology.** Every chart is a measurement of process
plus measurement system. If gauge repeatability and reproducibility consume
40% of the tolerance, the chart is substantially plotting the metrology tool.
MSA is a prerequisite for SPC, not an optional companion module.

**Enabling every run rule everywhere.** Each additional Western Electric or
Nelson rule raises the false-alarm rate. The full Nelson set on an in-control
process produces a signal roughly every 90 points instead of every 370. Tools
that ship with all rules on by default generate the alarm fatigue described
above.

**Unreproducible analysis.** A capability study whose input data has since been
overwritten, whose cleaning steps live in a deleted notebook cell, and whose
limits came from a spreadsheet cannot be defended in an audit — and in
automotive quality, undefendable means unusable.

## 3. What this project builds

An SPC monitoring platform that treats each of the above as a first-class
design constraint rather than a footnote:

| Capability | What it delivers |
|---|---|
| Control charting | I-MR, X̄-R, X̄-S, EWMA, CUSUM, and attribute charts (p, np, c, u), selected per parameter class rather than applied uniformly |
| Run-rule detection | Configurable Western Electric and Nelson rule sets, with the false-alarm cost of each configuration measured and documented |
| Process capability | Cp, Cpk, Pp, Ppk, Cpm with explicit short-term versus long-term sigma, non-normal handling, and mandatory reporting of n and window |
| Measurement system analysis | Gauge R&R (ANOVA method), bias, linearity, and stability — gating the trust placed in every other output |
| Variance decomposition | Nested analysis separating within-wafer, wafer-to-wafer, and lot-to-lot contributions, so improvement effort targets the dominant term |
| Spatial analysis | Wafer maps and radial/edge signature detection, since spatial patterns are invisible in a time series and often carry the root cause |
| Tool and chamber matching | Comparison across parallel tools and chambers, the most common source of an apparent process shift |
| Excursion workflow | Alarm acknowledgement, OCAP linkage, root-cause note, and disposition — producing the audit trail, not just the detection |

## 4. Who it is for

| User | What they need from it | Primary interface |
|---|---|---|
| **Process engineer** | "Is my process stable, and if it moved, when and on which tool?" | Control chart viewer, tool comparison, wafer map |
| **Quality engineer** | Capability evidence for a customer or a PPAP submission; MSA status; audit-ready records | Capability screen, MSA screen, report generation |
| **Equipment engineer** | Chamber-level behaviour, drift after maintenance, matched-tool deviation | Tool/chamber comparison, drift view |
| **Shift lead / operator** | "What needs attention right now, and what is the reaction plan?" | Line overview, alarm queue with OCAP linkage |
| **Quality manager** | Trend across areas, open excursions, systemic issues | Summary dashboards, generated reports |

The dashboard is designed for the shift lead's question first, because that is
the one asked most often and under the most time pressure.

## 5. Project purpose and success criteria

This is a **portfolio project**, built to demonstrate the competency profile of
an Advanced Quality Excellence Engineer in a European automotive-facing
semiconductor fab — specifically the intersection that is rare and therefore
valuable: applied statistics, semiconductor process knowledge, quality-system
fluency (IATF 16949, MSA, control plans, 8D/CAPA), and the software engineering
discipline to make analytics trustworthy in production.

It succeeds if a fab engineer reviewing it concludes:

1. **The statistics are right.** Verifiable against cited references, not
   asserted. This is why `tests/statistical/` exists as a separate tier.
2. **The domain is understood.** The distinctions that matter — control versus
   specification limits, short- versus long-term sigma, nested variance,
   rational subgrouping in a spatial context — are handled correctly and
   visibly, not glossed over.
3. **The engineering is production-grade.** Typed, tested, documented,
   reproducible, auditable. It reads like an internal manufacturing tool, not
   a tutorial.
4. **The quality-system thinking is present.** Audit trail, data integrity,
   traceability, reaction plans. A charting library is not a quality system.

It explicitly does **not** aim to be a commercial MES/YMS replacement, to
achieve real-time equipment control, or to compete on feature count with
established fab software.

## 6. Operating context and constraints

**No real fab data will ever be used.** Wafer-level measurement data is
customer-confidential in a foundry context and is not available outside a fab
regardless. All data is synthetic, generated by `scripts/simulation/` with
physically plausible variation structure and deliberately injected fault
signatures.

This constraint turns out to be an advantage. Because injected faults have
**known ground truth**, the detection engine can be *scored* — sensitivity,
average run length, false-alarm rate — rather than merely inspected by eye. A
real-data project could not make that claim.

**Deployment assumption: on-premises.** Semiconductor fabs do not send process
data to public cloud. The architecture assumes an on-prem, network-restricted
deployment with no external service dependencies at runtime. This is a
deliberate constraint, and it shapes the technology choices in
[TECH_STACK.md](TECH_STACK.md).

**Single developer, AI-assisted.** The project is built by one engineer working
with Cursor. This is why `.cursor/` and this documentation set exist: the AI
agent is treated as a contributor that must be onboarded through explicit,
retrievable knowledge rather than repeated inference.

## 7. Scope boundaries

| In scope | Out of scope |
|---|---|
| Univariate SPC across the standard chart family | Real-time equipment control or interlocks |
| Capability and MSA analysis | Full MES or YMS functionality |
| Synthetic fab data generation with known faults | Ingestion of real proprietary fab data |
| Excursion detection, disposition workflow, audit trail | Automated root-cause determination |
| Batch and scheduled analysis | Sub-second streaming from equipment |
| Multivariate methods (Hotelling T², PCA) — *stretch* | Full FDC / trace-data platform |
| Drift forecasting — *stretch, augmenting not replacing SPC* | Any model that overrides engineering judgement |

## 8. Guiding principles

1. **Correctness is proven, not asserted.** Every statistical result is
   validated against an independent reference.
2. **A false alarm is a defect.** Detection sensitivity and false-alarm rate
   are both measured, and both are acceptance criteria.
3. **Process knowledge is declarative.** Limits, rules, and tool registries are
   reviewable configuration, not code.
4. **Every number is reproducible and traceable.** Data revision, code
   revision, and configuration revision accompany every reported result.
5. **The engineer stays in the loop.** The platform surfaces evidence and
   supports a decision; it does not make the decision.

---

**Related:** [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) ·
[GLOSSARY.md](GLOSSARY.md) ·
[DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) ·
[QUALITY_ASSURANCE_PLAN.md](QUALITY_ASSURANCE_PLAN.md)
