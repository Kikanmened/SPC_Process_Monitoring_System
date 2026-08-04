# Risk Register

**Document owner:** Project lead
**Status:** Active — reviewed at each phase gate
**Last updated:** 2026-08-03

Risks to the project's success and to the correctness of what it produces.
Maintained in the format a quality organisation would recognise, because
managing risk on a quality tool with less rigour than the tool itself demands
would be an odd position to hold.

**Scoring:** Likelihood (1 rare – 5 near-certain) × Impact (1 negligible – 5
severe) = Score. Scores ≥ 12 require an active mitigation with a named trigger;
scores ≥ 20 are unacceptable and must be designed out rather than managed.

| Score | Band | Response |
|---|---|---|
| 20–25 | Unacceptable | Redesign to eliminate |
| 12–19 | High | Active mitigation, monitored trigger |
| 6–11 | Medium | Mitigation planned, reviewed at phase gates |
| 1–5 | Low | Accepted, documented |

---

## 1. Technical correctness risks

These carry the highest impact scores in the register. A defect here does not
crash — it produces a confident wrong number that someone acts on.

### R-01 · Incorrect statistical implementation
**Category:** Correctness · **L** 3 · **I** 5 · **Score 15 — High**

A control limit, capability index, or rule evaluation is subtly wrong. The
chart renders perfectly and the number is plausible, so it is not caught by
inspection or by conventional testing.

*Mitigation:* the statistical test tier — external reference values from
NIST/SEMATECH and Montgomery ([ADR-0017](DECISION_LOG.md#adr-0017)), both
publicly obtainable so any reviewer can verify them; hand-computed cases with
arithmetic shown in the docstring; analytical invariants under Hypothesis;
simulation-based ARL verification. Expected values may never be snapshots of
current output.
*Trigger:* any statistical test failure; any discrepancy between two estimators
that theory says must agree.
*Residual:* Low. This is the risk the entire testing strategy is built around.

### R-02 · Wrong estimator silently applied
**Category:** Correctness · **L** 3 · **I** 5 · **Score 15 — High**

Cpk computed from overall sigma, or control limits from long-term variation.
Nothing fails; the label simply misdescribes the number.

*Mitigation:* designed out at the API level — no function accepts a parameter
named `sigma`; callers must choose `sigma_within` or `sigma_overall`. Every
reported statistic carries its estimator. Enforced by
[CODING_STANDARDS.md](CODING_STANDARDS.md) §1.1 and by review.
*Trigger:* any proposed signature with an unqualified sigma parameter.
*Residual:* Low.

### R-03 · Specification limits used as control limits
**Category:** Correctness · **L** 2 · **I** 5 · **Score 10 — Medium**

The defining error of poor SPC tooling: the chart cannot detect a shift until
material is already non-conforming.

*Mitigation:* structurally impossible. `SpecificationLimit` and `ControlLimit`
are distinct types with no conversion and no shared accessor; the type checker
rejects substitution. The dashboard renders them with visually distinct
treatments.
*Residual:* Very low — the mistake cannot be expressed in the codebase.

### R-04 · Rational subgrouping error
**Category:** Correctness · **L** 4 · **I** 4 · **Score 16 — High**

Using within-wafer sites as a subgroup folds the systematic radial signature
into σ̂_within. Limits widen, the chart never signals, and the conclusion drawn
is that SPC does not work on this parameter.

*Likelihood is high because this is genuinely easy to get wrong* — it is the
intuitive choice, and the resulting chart looks entirely normal.

*Mitigation:* the synthetic generator produces a *systematic* spatial
signature, so a naive implementation fails its own detection benchmark rather
than passing quietly. Subgrouping strategy is recorded on every `Subgroup`
object. Documented in [GLOSSARY.md](GLOSSARY.md) and enforced by a
`.cursor/rules/` entry.
*Trigger:* σ̂_within materially exceeding the generator's configured
within-subgroup variance.
*Residual:* Medium — requires continued vigilance as new parameters are added.

### R-05 · Excessive false alarms
**Category:** Correctness · **L** 3 · **I** 4 · **Score 12 — High**

Too many rules enabled, or a rule implemented with an off-by-one window. Alarm
fatigue follows, and operators stop trusting the system. Treated here as a
defect class, not a training issue.

*Mitigation:* ARL₀ measured by simulation for every configured rule set and
asserted within ±15% of theory. Any configuration change must state its ARL
impact.
*Trigger:* measured ARL₀ outside tolerance; observed signal rate exceeding
prediction.
*Residual:* Low.

### R-06 · Silent data corruption in the pipeline
**Category:** Correctness · **L** 3 · **I** 5 · **Score 15 — High**

A malformed record coerced into a plausible float; a unit mismatch applied
silently; a duplicate dropped. The chart is wrong and nothing reports it.

*Mitigation:* Pandera validation at every zone boundary as a hard stop with
quarantine. Units stored explicitly, never inferred. Duplicates fail the run.
Full lineage per row and per run.
*Trigger:* any validation failure; any row-count mismatch across a stage.
*Residual:* Low.

### R-07 · Automatic outlier removal deleting real signal
**Category:** Correctness · **L** 2 · **I** 5 · **Score 10 — Medium**

Standard practice in general data science, actively harmful here: an outlier
may be precisely the excursion the platform exists to detect.

*Mitigation:* outliers are flagged, never auto-removed. Any removal is an
explicit engineering decision recorded in the audit trail.
*Residual:* Very low.

### R-08 · Capability reported on an unstable process
**Category:** Correctness · **L** 3 · **I** 4 · **Score 12 — High**

Cpk computed on an out-of-control process describes a distribution that does
not exist, yet reads as authoritative.

*Mitigation:* application-layer policy refuses to produce a capability report
without a stability precondition. The refusal path is tested.
*Trigger:* any request for capability on a parameter with open violations in
the window.
*Residual:* Low.

## 2. Project execution risks

### R-10 · Scope expansion beyond sustainable completion
**Category:** Execution · **L** 4 · **I** 3 · **Score 12 — High**

The domain is deep and every direction is interesting. A half-finished
multivariate SPC module is worth less than none, because it raises the question
of what else is half-finished.

*Mitigation:* explicit scope boundaries in
[PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) §7; advanced analytics confined to
Phase 15 and gated on everything before it being complete; phase exit criteria
are demonstrable, not subjective. Capabilities that exceed the requirement
baseline are recorded as proposed requirements rather than absorbed
([MODULE_DESIGN.md](MODULE_DESIGN.md) §5).
*Trigger:* work starting on a Phase 15 item before Phase 14 exit criteria are
met, or on a proposed requirement before the PRD is amended.
*Residual:* Medium — this is the most likely way the project underdelivers.

### R-11 · Foundation work displacing visible progress
**Category:** Execution · **L** 3 · **I** 2 · **Score 6 — Medium**

Six phases produce no application logic. Motivation can suffer, and an
observer may see an elaborate empty repository.

*Mitigation:* the foundation phases are themselves portfolio evidence — the
documentation set demonstrates exactly the systems thinking the target role
requires. Phase 8 produces visible output early. Accepted deliberately:
retrofitting `mypy --strict`, the layering rules, or the audit trail later
costs multiples of doing it now.
*Residual:* Low.

### R-12 · Documentation drifting from implementation
**Category:** Execution · **L** 4 · **I** 3 · **Score 12 — High**

Fifteen documents written before the code is a large surface for divergence.
Stale documentation is worse than none: it is confidently wrong and it will be
followed — by a human, and more readily by the agent.

*Mitigation:* documentation updates in the same pull request as the change;
link checking in CI; a documentation-currency item on the review checklist;
phase-gate review of the whole set.
*Trigger:* any merged PR changing behaviour without a documentation diff.
*Residual:* Medium — the most persistent risk in the register, and it never
fully closes.

### R-13 · Single-contributor knowledge concentration
**Category:** Execution · **L** 5 · **I** 2 · **Score 10 — Medium**

No second reviewer to catch a domain misconception. A statistical
misunderstanding could propagate through the whole engine unchallenged.

*Mitigation:* external references act as the second reviewer — every
statistical claim is checked against published values rather than against the
author's belief. Decision records force the reasoning to be written down and
therefore examinable.
*Residual:* Medium. Genuinely mitigated by the reference-validation approach,
but not eliminated.

## 3. AI-assisted development risks

### R-20 · Plausible fabrication of statistical constants
**Category:** AI · **L** 4 · **I** 5 · **Score 20 — Unacceptable, designed out**

The characteristic failure mode of generated code in this domain. An AI-written
`d2 = 1.182` for n=2 (correct value 1.128) looks entirely authoritative and is
unverifiable by reading. This is the highest-scoring risk in the register.

*Mitigation — designed out, not managed:*
- Every constant lives in `analytics/estimators/` with a citation; a constant
  without a source is not merged.
- Every constant is verified by a reference-validated test.
- A `.cursor/rules/` entry forbids writing any uncited constant or formula.
- Review explicitly checks constants against the Montgomery appendix tables and
  the NIST/SEMATECH handbook — both obtainable by the reviewer, which is what
  makes the check real rather than nominal.
*Trigger:* any numeric literal in analytics code lacking a citation.
*Residual:* Low — but only because every one of the above is in place.

### R-21 · Helpful fallbacks reintroducing silent failure
**Category:** AI · **L** 4 · **I** 4 · **Score 16 — High**

Generated code tends toward defensive `try`/`except`, default values, and
graceful degradation — exactly the silent-failure patterns banned by
[CODING_STANDARDS.md](CODING_STANDARDS.md) §1.4. Each one converts a visible
error into a fabricated number.

*Mitigation:* explicit `.cursor/rules/` prohibition; Ruff rules against bare
except; review checklist item; the fail-fast principle stated in every relevant
document.
*Trigger:* any `except` without a specific type; any `or DEFAULT_` pattern in a
quality-critical path.
*Residual:* Medium — requires sustained review attention.

### R-22 · Architectural drift under AI contribution
**Category:** AI · **L** 3 · **I** 3 · **Score 9 — Medium**

An agent solving a local problem imports across a layer boundary because it is
the shortest path.

*Mitigation:* `import-linter` enforces the dependency rule mechanically in CI.
Convention alone would not survive.
*Residual:* Very low — this is a solved problem once the check exists.

### R-23 · Agent context degradation as the codebase grows
**Category:** AI · **L** 3 · **I** 2 · **Score 6 — Medium**

Larger codebase, more inference, more inconsistency, higher token cost.

*Mitigation:* `.cursor/` rules and context files; path-scoped rules so only
relevant constraints load; documentation written in retrievable fragments
rather than long monoliths.
*Residual:* Low.

## 4. Data and confidentiality risks

### R-30 · Synthetic data insufficiently realistic
**Category:** Data · **L** 3 · **I** 4 · **Score 12 — High**

If the generator emits independent Gaussian noise, detection becomes trivial,
every benchmark score is meaningless, and the project's central correctness
claim collapses.

*Mitigation:* nested variance structure with systematic spatial signature,
fixed tool and chamber offsets, slot effects, and a separate gauge error term
([DATASET_GUIDE.md](DATASET_GUIDE.md) §4.2). Phase 8 exit criteria require that
variance decomposition recovers the configured components.
*Trigger:* detection rates implausibly close to 100% at small shift magnitudes.
*Residual:* Medium — realism is a matter of degree and warrants periodic
review.

### R-31 · Accidental commit of confidential or secret material
**Category:** Confidentiality · **L** 2 · **I** 5 · **Score 10 — Medium**

*Mitigation:* `gitleaks` in pre-commit and CI; no real fab data by policy;
fictional identifiers throughout; data zones git-ignored; `configs/secrets/`
holds templates only.
*Residual:* Very low.

### R-32 · Loss of audit trail integrity
**Category:** Compliance · **L** 2 · **I** 4 · **Score 8 — Medium**

Audit records rotated away with operational logs, or mutated in place. In a
regulated context this is an audit finding rather than an inconvenience.

*Mitigation:* audit records are a separate sink with separate retention,
append-only, exported to durable storage by a scheduled job.
*Residual:* Low.

## 5. Operational and technical risks

### R-40 · Performance failure at production volume
**Category:** Operational · **L** 3 · **I** 3 · **Score 9 — Medium**

Per-point Python loops are roughly two orders of magnitude too slow for the
target volume.

*Mitigation:* vectorised computation as a design rule; explicit budgets in
[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §7 asserted in
`tests/performance/`.
*Trigger:* any benchmark regression beyond threshold.
*Residual:* Low.

### R-41 · Dependency supply-chain compromise or abandonment
**Category:** Technical · **L** 2 · **I** 3 · **Score 6 — Medium**

*Mitigation:* committed lockfile with frozen production installs; `pip-audit`
on every PR and weekly; minimal direct dependencies, each justified; the
domain layer is near-dependency-free by design.
*Residual:* Low.

### R-42 · Streamlit and Plotly constraints limiting the interface
**Category:** Technical · **L** 3 · **I** 2 · **Score 6 — Medium**

Layout and session-state limitations may prove restrictive, most plausibly for
the wafer map and the alarm queue. Narrowed by
[ADR-0018](DECISION_LOG.md#adr-0018), which settles the wafer map as
interactive Plotly and leaves rendering performance at high point counts as the
residual concern.

*Mitigation:*
- **Structural:** the dashboard is a client of the application layer with zero
  statistical logic, so replacing the renderer touches presentation only
  ([ADR-0006](DECISION_LOG.md#adr-0006)).
- **A `WaferMapView` value object** feeds both the interactive figure and the
  static export, so the two cannot diverge and a renderer swap affects one
  consumer.
- **Point budget** capping individually rendered site markers at ~5 000 per
  figure, degrading to an aggregated view above it and stating so on screen.
  Unfiltered wafer map queries are rejected rather than attempted.
- **Cache keys include data and configuration revision**, so a recalculated
  baseline or reprocessed data invalidates automatically.
- A `tests/performance/` case pins the rendering budget from Phase 12.

*Trigger:* wafer map render exceeding the interaction budget at or below the
point cap; any Streamlit session-state workaround that would require logic in
`dashboard/`.
*Residual:* Low — the cost of being wrong here was deliberately minimised.

### R-43 · Visualisation fabricating a spatial signature
**Category:** Correctness · **L** 3 · **I** 4 · **Score 12 — High**

Two rendering choices can make a wafer map show a pattern that is not in the
data. A perceptually non-uniform colour map (rainbow, jet) introduces sharp
perceived boundaries across smooth data, manufacturing an apparent edge ring or
radial band. Per-wafer colour autoscaling makes every wafer look alike,
concealing the differences that cross-wafer comparison exists to reveal.

Rated as a correctness risk rather than a presentation one: the wafer map is a
detection surface, and a rendering that invents or conceals a signature
produces a wrong engineering conclusion just as surely as a wrong control
limit — while being far less likely to be questioned, because it is "just a
chart".

*Mitigation:* fixed colour scale limits across any comparison set, displayed
numerically; per-wafer autoscaling only as an explicit, labelled user action;
perceptually uniform, colour-vision-safe scales only — sequential (viridis,
cividis) for values, diverging centred on target for deviation
([ADR-0018](DECISION_LOG.md#adr-0018)).
*Trigger:* any proposed colour scale outside the approved set; any autoscaling
applied without an explicit label.
*Residual:* Low.

---

## Risk summary

23 risks recorded.

| Score | Count | IDs |
|---|---|---|
| Unacceptable (20–25) | 1 | R-20 *(designed out; residual Low)* |
| High (12–19) | 11 | R-01, R-02, R-04, R-05, R-06, R-08, R-10, R-12, R-21, R-30, R-43 |
| Medium (6–11) | 11 | R-03, R-07, R-11, R-13, R-22, R-23, R-31, R-32, R-40, R-41, R-42 |

**The three requiring most sustained attention:** R-04 (subgrouping error — easy
to get wrong, invisible when wrong), R-12 (documentation drift — never fully
closes), and R-21 (AI-introduced silent fallbacks — needs review attention on
every change).

Note the pattern in the High band: R-04, R-30, and R-43 are all cases where a
mistake produces a *plausible-looking wrong answer* rather than a failure —
inflated control limits that never signal, synthetic data too easy to detect
against, and a rendering that invents a spatial pattern. That class of defect is
what this project's controls are principally aimed at.

## Review cadence

Reviewed at every phase gate and whenever a defect reveals a risk not listed.
A defect that maps to no entry here is itself a finding: the register was
incomplete, and the gap is added along with the fix.

---

**Related:** [QUALITY_ASSURANCE_PLAN.md](QUALITY_ASSURANCE_PLAN.md) ·
[DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md) ·
[TESTING_STRATEGY.md](TESTING_STRATEGY.md) ·
[DECISION_LOG.md](DECISION_LOG.md)
