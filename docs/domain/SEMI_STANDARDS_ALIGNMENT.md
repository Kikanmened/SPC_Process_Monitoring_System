# SEMI Standards Alignment

**Document owner:** Project lead
**Status:** Active — conceptual alignment, no implementation claim
**Last updated:** 2026-08-04

Layer 3 of the reference hierarchy in
[ADR-0017](../DECISION_LOG.md#adr-0017). This document records which SEMI
standards shape the platform's vocabulary, data model, and interface design,
and — equally important — what is *not* being claimed.

---

## 1. Why this matters, and the constraint

A tool built for semiconductor manufacturing should speak the language a fab
already speaks. SEMI standards are that language: they define equipment states,
productivity metrics, communication protocols, substrate tracking, and data
collection conventions that every fab and every equipment vendor already shares.
A platform that invents its own parallel vocabulary for concepts SEMI already
standardises creates a translation burden at every integration point and marks
itself, immediately, as built by someone outside the industry.

**The constraint:** SEMI standards are controlled publications, distributed
under licence. They are therefore **Layer 3 — conceptual alignment only**:

- **Never reproduced.** No standard text, table, or specification content
  appears in this repository.
- **Never a numerical test dependency.** No expected value in
  `tests/statistical/` cites a SEMI standard. That role belongs exclusively to
  Layer 1 (NIST/SEMATECH and Montgomery).
- **Never a compliance claim.** Alignment with a vocabulary is not conformance,
  and this project does not assert conformance to any SEMI standard.

What alignment *does* mean: when this platform names a concept that SEMI has
already defined, it uses SEMI's name and SEMI's meaning.

## 2. Equipment state and performance

### SEMI E10 — Reliability, Availability, Maintainability (RAM)

Defines the standard equipment state model — non-scheduled time, unscheduled
downtime, scheduled downtime, engineering time, standby time, and productive
time — together with the availability, reliability (MTBF), and maintainability
(MTTR) metrics derived from it.

**This one has a genuine architectural consequence, not merely a terminological
one.** Equipment state is *context for interpreting a control chart*:

- **Step shifts cluster at state transitions.** The single most common physical
  explanation for a sudden mean shift is a return to productive time after
  scheduled maintenance, a chamber clean, or a part replacement. A chart that
  cannot show when the tool was down forces the engineer to correlate by hand
  against a separate system, which is the friction that makes SPC tools go
  unused.
- **Baseline qualification must respect equipment state.** A qualified baseline
  represents stable productive operation. Data spanning engineering time — a
  deliberate experiment — is not stable operation, and including it inflates
  the control limits with variation that was intentional. See
  [GLOSSARY.md](../GLOSSARY.md) on *Baseline*.
- **Excursion investigation starts with state history.** "What changed?" is
  frequently answered by "the tool came back from an unscheduled down."

The `Tool` and `Chamber` entities therefore carry an equipment state history
using E10 state names, and the control chart viewer annotates state transitions
on the time axis. The platform does not *compute* E10 availability metrics —
that is an equipment-engineering function belonging in a different system — but
it consumes and displays state so that process signals can be read in context.

### SEMI E79 — Equipment productivity and OEE

Defines Overall Equipment Efficiency as the product of availability,
performance, and quality efficiency components, along with the underlying
productivity definitions.

**Explicitly out of scope as a feature.** This is an SPC platform, not an OEE
reporting tool, and building a half-complete OEE module would be exactly the
scope expansion [RISK_REGISTER.md](../RISK_REGISTER.md) R-10 warns about.

The alignment is forward-looking and cheap: the **quality efficiency**
component of OEE is a function of conforming output, which is precisely what
this platform measures. If an OEE capability is ever added — or, more likely,
if this platform ever feeds one — the vocabulary already matches and no
translation layer is needed. Recording that now costs a paragraph; discovering
it later costs a refactor.

### SEMI E58 (ARAMS) and E116 (Equipment Performance Tracking)

Automated reliability and availability reporting, and real-time equipment
performance state tracking. Relevant as the *sources* from which equipment
state would arrive in a real deployment. The infrastructure port for equipment
state is designed with these in mind, so a future adapter has a defined shape
to fill rather than a schema invented from scratch.

## 3. Equipment communication and data collection

| Standard | Subject | Relevance here |
|---|---|---|
| **E5** (SECS-II) | Message content for equipment communication | The classical fab equipment interface; the vocabulary any real ingestion adapter must speak |
| **E30** (GEM) | Generic Equipment Model — states, collection events, alarms | Defines how equipment reports events and data; shapes the event model an adapter would map from |
| **E37** (HSMS) | High-speed SECS message services over TCP/IP | Transport for the above |
| **E120** (CEM) | Common Equipment Model | Structural model of equipment, modules, and subsystems — the tool/chamber hierarchy in `domain/` follows this shape |
| **E125** (EqSD) | Equipment self-description | How equipment declares its own structure and capabilities |
| **E132** | Authentication and authorisation | Access control conventions for equipment data |
| **E134** (DCM) | Data collection management — plans, triggers, buffering | The model a high-volume measurement feed would follow |
| **E164** | EDA common metadata | Consistent metadata across equipment data sources |

Together, E120/E125/E132/E134 form **Interface A / EDA**, the modern
high-volume equipment data collection framework. This platform does not
implement them. It does define its measurement ingestion port so that an EDA
adapter is a plausible future implementation rather than an impossible one —
which is the difference between an extension point and a wish.

The concrete consequence today is in the domain model: the tool → chamber
hierarchy in `src/spc_platform/domain/` mirrors the equipment/module structure
these standards describe, rather than a flat equipment identifier. That is why
`chamber_id` is a first-class field on every measurement
([DATASET_GUIDE.md](../DATASET_GUIDE.md) §3.1), and why chamber-level
comparison is a design feature rather than an afterthought.

## 4. Material tracking and substrate mapping

| Standard | Subject | Relevance here |
|---|---|---|
| **E90** | Substrate tracking — identity and location through the process | The lot/wafer/slot model, and why slot position is a first-class field rather than an index |
| **E142** | Substrate mapping — structured representation of per-site wafer data | Directly relevant to the wafer map feature and to how site coordinates are represented |

Wafer map data has established industry representations, of which E142 is the
structured-mapping specification. This matters for the spatial analysis feature:
site coordinates are stored as true positions in millimetres from wafer centre
rather than as an opaque site index, so the data model can express a real
substrate map rather than an internal convention that would need translating at
every boundary. It also bears on open question **Q4** (wafer map rendering) —
the *representation* decision is settled by following the industry model, and
only the *rendering* approach remains open.

## 5. Time synchronisation

### SEMI E148 — Time synchronisation

Defines time synchronisation requirements across fab equipment.

Directly reinforces a rule already stated in
[CODING_STANDARDS.md](../CODING_STANDARDS.md): **naive datetimes are banned by
lint rule**, and every timestamp is timezone-aware.

The reason is not pedantry. Measurements arrive from process tools and metrology
tools that are physically separate systems with independent clocks. Clock skew
between them produces series that appear misordered, which manifests as a
control chart with points in the wrong sequence — and a run rule evaluated over
a misordered series produces a signal that corresponds to nothing. It is a
failure mode that looks like a statistical defect and is actually a data
integrity defect, and telling them apart afterwards is expensive.

## 6. Where each standard touches the codebase

| Area | Standards informing it |
|---|---|
| `domain/` tool and chamber hierarchy | E120, E125 |
| `domain/` lot, wafer, slot model | E90 |
| Site coordinates and wafer maps | E142 |
| Equipment state history and chart annotation | E10, E116 |
| Timestamp handling | E148 |
| Future measurement ingestion adapter | E5, E30, E37, E134, E164 |
| Future OEE or productivity integration | E79, E58 |

## 7. What is not claimed

Stated plainly, because overstating alignment would undermine the credibility
the alignment is meant to establish:

- **No conformance claim.** This platform does not implement, certify against,
  or claim conformance to any SEMI standard.
- **No standard content is reproduced.** Concept names and structural ideas
  only, drawn from publicly available descriptions of the standards' scope.
- **No SEMI-sourced numerical expectation** appears in any test.
- **No implementation** of SECS/GEM, EDA, E10 metric computation, or OEE
  reporting exists or is planned within the current scope
  ([PROJECT_CONTEXT.md](../PROJECT_CONTEXT.md) §7).

The claim being made is narrow and, precisely because it is narrow, defensible:
**where this platform names something a fab already names, it uses the fab's
name.**

---

**Related:** [../DECISION_LOG.md](../DECISION_LOG.md#adr-0017) ·
[../GLOSSARY.md](../GLOSSARY.md) ·
[../SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) ·
[../DATASET_GUIDE.md](../DATASET_GUIDE.md)
