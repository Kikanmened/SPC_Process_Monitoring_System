# Module 7 — Root Cause Analysis

**Owning layers:** `analytics/comparison/`, `analytics/commonality/`, `analytics/variance/`, `application/`, `domain/`
**Depends on:** Modules 2, 3, 6, 10
**Depended on by:** Modules 5, 9
**Requirement coverage:** FR-T01 – FR-T03, FR-S07, FR-A02 – FR-A04, FR-A07; NFR-CO02. **Proposed and not approved:** FR-RC01 – FR-RC04
**Delivered in:** Phase 9 (analytics), Phase 11 (workflow), Phase 13 (excursion closure) · **Status:** Design — partially proposed scope

---

## Purpose

Assemble the evidence an engineer needs to reach a conclusion about an
excursion, and record the conclusion they reach.

**The platform does not determine causes.** That is a deliberate non-goal
([SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) §10, PRD §6.3), and the
reasoning is operational rather than technical: a system that asserts a cause it
cannot justify will be overridden once and ignored thereafter. What the module
does is gather the comparisons a competent engineer would run — commonality
across tool, chamber, recipe and material; matched-tool deviation; variance
decomposition; spatial signature; equipment state history — each with its
statistical test, effect size, and sample size stated, so the engineer can judge
the strength of each rather than being handed a verdict.

The module also owns the excursion record itself: acknowledgement, OCAP linkage,
disposition with a mandatory reason, and closure with an 8D or CAPA reference.
That is the quality-system half of root cause, and it is where the human
conclusion is captured with attribution.

### Scope status

The individual computations are required today (FR-T01, FR-T02, FR-S07). Their
assembly into one evidence artefact is not, so the following are **proposed and
not in the PRD**:

| Proposed | Requirement |
|---|---|
| FR-RC01 | Assemble an evidence bundle for an excursion from commonality, matched-tool comparison, variance decomposition, spatial signature, and equipment state history |
| FR-RC02 | Every evidence item states its statistical test, effect size, sample size, and uncertainty |
| FR-RC03 | The platform never asserts a cause; a cause is recorded only as an attributed human conclusion |
| FR-RC04 | An evidence bundle reports insufficient evidence explicitly rather than presenting the strongest weak signal as a finding |

## Responsibilities

- Compare matched parameters across parallel tools and chambers with a **stated**
  statistical test, never an unlabelled difference (FR-T01).
- Perform commonality analysis across tool, chamber, recipe, and material for a
  set of affected lots (FR-T02).
- Surface chamber-level resolution wherever tool-level data is shown (FR-T03) —
  chamber mismatch is a leading explanation for an apparent process shift, and
  it is invisible at tool granularity.
- Decompose variance into within-wafer, wafer-to-wafer, and lot-to-lot
  components, and where the design supports it, tool and chamber components
  (FR-S07, BO-5).
- Correlate the excursion window with equipment state transitions in SEMI E10
  terms; a return to productive time after maintenance is the most common
  physical explanation for a sudden mean shift.
- Assemble the above into one evidence bundle, ranked by **evidence strength,
  explicitly not by likelihood of being the cause**.
- Record the excursion lifecycle: acknowledgement with actor and timestamp
  (FR-A02), disposition with a mandatory reason from the permitted set
  (FR-A03), OCAP linkage (FR-A04), and 8D or CAPA reference on closure (FR-A07).
- Emit an audit record for every state change in that lifecycle.

**Not this module's work:** raising the signal (Modules 3 and 6), ordering the
alarm queue or notifying anyone (Module 9), and concluding (the engineer).

## Public interfaces

```python
def compare_entities(
    series_by_entity: Mapping[EntityId, MeasurementSeries],
    test: ComparisonTest,
) -> ComparisonEvidence:
    """Matched tool or chamber comparison. The test is chosen by the caller and reported."""


def commonality(
    affected: Sequence[LotId],
    unaffected: Sequence[LotId],
    dimensions: Sequence[CommonalityDimension],
) -> CommonalityEvidence:
    """Association between an outcome and tool, chamber, recipe, or material."""


def decompose_variance(data: NestedMeasurements, model: VarianceModel) -> VarianceComponents:
    """Within-wafer, wafer-to-wafer, lot-to-lot, and where modelled, tool and chamber."""


def assemble_evidence(excursion: Excursion, sources: EvidenceSources) -> EvidenceBundle:
    """One bundle of independent evidence items. Contains no cause field."""
```

`EvidenceBundle` has no attribute in which a cause could be recorded. The
constraint is structural rather than a review item, in the same spirit as the
specification/control limit separation. A cause reaches the record only through
`RecordDisposition`, which requires an actor.

| Exception | Raised when |
|---|---|
| `InsufficientEvidenceError` | No comparison in the bundle meets its configured minimum n — surfaced as a stated outcome, not an empty bundle |
| `UnmatchedComparisonError` | Entities are not comparable: different recipe, product, or spec in force |
| `DispositionRequiredError` | Closure is attempted without a disposition and reason (AC-B2) |
| `UnknownDispositionError` | A disposition outside the permitted set: continue, hold, rework, scrap, use-as-is |

## Dependencies

| Depends on | For |
|---|---|
| Module 2 | Series by tool, chamber, recipe, product; nested data for variance decomposition |
| Module 3 | The violations that opened the excursion, and the limits in force at the time |
| Module 6 | Spatial signature classification as one evidence item |
| Module 10 | Comparison policy, minimum n, OCAP references, audit sink, injected clock |
| statsmodels, SciPy | ANOVA, variance components, hypothesis tests |

## Expected inputs

| Input | Source | Notes |
|---|---|---|
| Excursion and its violations | Violation repository | With the baseline in force when raised (FR-AU04) |
| Comparable series | Module 2 | Matched on recipe and product, or the comparison is refused |
| Equipment state history | Tool and chamber records | SEMI E10 states with timezone-aware transitions |
| Control plan | `data/reference/control_plans.yaml` | OCAP reference per characteristic |
| Comparison policy | `configs/base/` | Permitted tests, minimum n, significance conventions |

## Expected outputs

| Output | Consumer | Contents |
|---|---|---|
| `EvidenceBundle` | Module 9, reports | Independent evidence items, each with test, effect size, n, uncertainty; or an explicit insufficient-evidence outcome |
| `VarianceComponents` | Modules 5, 9 | Component estimates with the model and method named (BO-5) |
| `Excursion` | Modules 5, 9 | Lifecycle state, acknowledgement, disposition, reason, OCAP, 8D/CAPA reference |
| Audit records | `logs/audit/` | Every lifecycle transition with actor, timestamp, before and after, reason |

## Files to create

```
src/spc_platform/analytics/comparison/__init__.py
src/spc_platform/analytics/comparison/matched_entities.py    tool and chamber comparison
src/spc_platform/analytics/comparison/tests.py               permitted tests, each named
src/spc_platform/analytics/commonality/__init__.py
src/spc_platform/analytics/commonality/association.py
src/spc_platform/analytics/variance/__init__.py
src/spc_platform/analytics/variance/nested.py                variance components
src/spc_platform/domain/excursion.py
src/spc_platform/domain/disposition.py
src/spc_platform/domain/evidence.py                          EvidenceBundle, EvidenceItem
src/spc_platform/application/use_cases/assemble_root_cause_evidence.py
src/spc_platform/application/use_cases/acknowledge_violation.py
src/spc_platform/application/use_cases/record_disposition.py
src/spc_platform/application/use_cases/close_excursion.py
src/spc_platform/application/ports/excursion_repository.py
src/spc_platform/infrastructure/repositories/excursion_repository.py
configs/base/root_cause.yaml                                 permitted tests, minimum n
```

## Testing requirements

| Tier | What it must establish |
|---|---|
| `statistical/` | Variance decomposition recovers the components configured in the generator, within tolerance — the same property that gates Phase 8's exit criteria. Comparison tests reproduce published worked examples. |
| `unit/` | An excursion cannot be closed without a disposition and reason. A disposition outside the permitted set raises. Every lifecycle transition emits exactly one audit record. |
| `unit/` | `EvidenceBundle` exposes no cause attribute, and no code path populates one. A structural test, because this is the constraint most likely to erode under a helpful refactor. |
| `unit/` | Insufficient evidence is reported as such rather than returning the strongest available weak signal. |
| `contract/` | Every evidence item carries test, effect size, n, and uncertainty; the test fails if any is absent. |
| `e2e/` | Detection through acknowledgement, evidence assembly, disposition, and closure, with a complete audit trail at the end. |

## Documentation required

- `docs/api/root-cause.md` — the evidence contract and the excursion lifecycle
  state machine.
- `docs/quality/excursion-workflow.md` — detection, containment, investigation,
  disposition, closure, and how it maps to ISO 9001 8.7 and 10.2
  ([QUALITY_ASSURANCE_PLAN.md](../QUALITY_ASSURANCE_PLAN.md) §2).
- `docs/runbooks/excursion-response.md` — what a shift lead does, and what the
  platform will and will not tell them.
- An ADR if the no-cause-assertion constraint is ever revisited. It is a product
  position, not an implementation detail.

## Future extension points

- **Automated commonality across more dimensions** — material lot, operator,
  queue time, and preventive maintenance events, behind the same evidence
  contract (PRD §14, "Next").
- **Additional comparison tests** — registered with their assumptions, so the
  reported test name stays meaningful.
- **Recurrence linkage** — connecting an excursion to prior occurrences of the
  same signature, feeding Module 5's recurrence KPI.
- **Effectiveness verification** — did the corrective action hold? Measurable
  from the same history, and the natural completion of the ISO 9001 10.2 loop.
- **FDC and trace-data evidence** — a separate platform today; if it arrives, it
  enters as another evidence source, not another conclusion.

---

**Related:** [MODULE_DESIGN.md](../MODULE_DESIGN.md) ·
[06-anomaly-detection.md](06-anomaly-detection.md) ·
[09-dashboard-and-reporting.md](09-dashboard-and-reporting.md) ·
[QUALITY_ASSURANCE_PLAN.md](../QUALITY_ASSURANCE_PLAN.md)
