# Module 8 — Change Control Simulation

**Owning layers:** `application/`, `analytics/impact/`, `domain/`
**Depends on:** Modules 3, 4, 6, 10
**Depended on by:** Module 9
**Requirement coverage:** FR-R06, FR-CF03, FR-CF04, FR-AU04. **Proposed and not approved:** FR-CC01 – FR-CC06
**Delivered in:** Phase 11 · **Status:** Design — largely proposed scope

---

## Purpose

Answer, before a change is approved, what that change would have done.

Changing a control limit, a sigma estimator, a rule set, or a specification
limit **retroactively alters the meaning of every historical number**
([QUALITY_ASSURANCE_PLAN.md](../QUALITY_ASSURANCE_PLAN.md) §6). A rule set
addition that looks harmless can take ARL₀ from roughly 370 to roughly 91,
tripling the false-alarm rate and starting the slide into alarm fatigue that
ends with the real alarm being dismissed along with the rest (BO-2, R-05).

This module replays history under both the current and the proposed
configuration and reports the difference, so approval is an informed decision
rather than an optimistic one. It also owns the baseline lifecycle: qualifying a
stable window, computing the new limits through Module 3, versioning the result
with approver and effective date, and superseding — never overwriting — the
previous version.

### Scope status

FR-R06 requires an ARL impact statement for a rule set change, and FR-CF04 and
FR-AU04 require versioned, retained baselines. Nothing in the PRD requires the
machinery that produces an impact statement or replays history under a proposed
configuration. The following are **proposed and not in the PRD**:

| Proposed | Requirement |
|---|---|
| FR-CC01 | Record every proposed change as a change request: proposer, type, current value, proposed value, and reason |
| FR-CC02 | Replay a defined historical window under current and proposed configuration and report the differences |
| FR-CC03 | Require an impact statement before approval, for every change type — generalising FR-R06 beyond rule sets |
| FR-CC04 | Label simulation output as simulated; it can never become a baseline, a violation, or a reported result |
| FR-CC05 | Record approval with actor, timestamp, and effective date; retain the superseded version |
| FR-CC06 | A replay is deterministic: the same data, code, and configuration revisions produce the same result |

## Responsibilities

- Record change requests for the four change types the platform controls:
  control limit or baseline, rule set, chart configuration, and specification
  limit.
- Replay a historical window under the current and the proposed configuration,
  reporting: measured ARL₀ before and after, violations that would appear,
  violations that would disappear, and the affected parameters, lots, and tools.
- Qualify a candidate baseline window, **excluding engineering time** rather than
  absorbing deliberate experimental variation into the control limits (SEMI E10,
  [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) §9).
- Create a new baseline version through Module 3's limit computation, record
  approver and effective date, supersede the prior version, and retain it so a
  historical violation still resolves against the limits in force when it was
  raised (AC-D1).
- Report which existing baselines, reports, and historical comparisons a change
  would invalidate.
- Keep simulated results structurally separate from real ones. A simulation
  writes to no production store and produces types that cannot be persisted as a
  `Baseline` or a `Violation`.
- Emit an audit record for the request, the impact statement, and the approval
  or rejection.

**Not this module's work:** computing limits or evaluating rules — that is
Module 3, called with alternative configuration. This module orchestrates and
compares; it implements no statistics of its own beyond differencing.

## Public interfaces

```python
def simulate_change(
    request: ChangeRequest,
    window: ReplayWindow,
    current: EffectiveConfiguration,
) -> ChangeImpact:
    """Replay history under current and proposed configuration and report the delta."""


def qualify_baseline_window(
    series: MeasurementSeries,
    policy: QualificationPolicy,
    state_history: EquipmentStateHistory,
) -> BaselineCandidate:
    """Propose a stable window, excluding engineering time. Refuses if none qualifies."""


def approve_baseline(candidate: BaselineCandidate, approval: Approval) -> BaselineVersion:
    """Create the new version, supersede the previous, and write the audit record."""
```

`ChangeImpact` is a distinct type from any production result and carries a
`simulated: Literal[True]` marker that no production writer accepts. Simulation
leaking into the audited path would be the most damaging failure this module
could have, so it is prevented by the type system rather than by care.

| Exception | Raised when |
|---|---|
| `NoQualifyingWindowError` | No stable period meets the qualification policy; carries what failed |
| `ImpactStatementRequiredError` | Approval is attempted before an impact statement exists (FR-R06, FR-CC03) |
| `UnauthorisedApprovalError` | The actor lacks the baseline approval role (NFR-SE04) |
| `ReplayDeterminismError` | Recorded revisions do not reproduce the recorded result |

## Dependencies

| Depends on | For |
|---|---|
| Module 3 | Limit computation and rule evaluation under alternative configuration; measured ARL₀ |
| Module 4 | Capability under a proposed specification limit change |
| Module 6 | Per-detector false-alarm characteristics feeding the impact statement |
| Module 10 | Effective configuration with its revision hash, authorisation, audit sink, clock |
| `domain/` | `Baseline`, `ControlLimit`, `SpecificationLimit`, `ChangeRequest`, `Approval` |

## Expected inputs

| Input | Source | Notes |
|---|---|---|
| Change request | Application caller | Type, current value, proposed value, reason, proposer |
| Replay window | Application caller | Timezone-aware bounds and the parameters in scope |
| Historical series | Module 2 | Pinned by data revision so the replay is reproducible |
| Current effective configuration | Module 10 | With its revision hash |
| Equipment state history | Tool records | To exclude engineering time from a candidate window |
| Qualification policy | `configs/spc/` | Minimum n, stability criteria, permitted state codes |

## Expected outputs

| Output | Consumer | Contents |
|---|---|---|
| `ChangeImpact` | Module 9, approver | ARL₀ before and after, violations added and removed, affected entities, invalidated artefacts, revisions, `simulated` marker |
| `BaselineCandidate` | Approver | Proposed window, computed limits, estimator, n, excluded intervals and why |
| `BaselineVersion` | Modules 3, 9 | New active version with approver, effective date, and a pointer to the superseded version |
| Audit records | `logs/audit/` | Request, impact statement, approval or rejection, supersession (QA plan §2.2) |

## Files to create

```
src/spc_platform/analytics/impact/__init__.py
src/spc_platform/analytics/impact/replay_delta.py         violation set differencing
src/spc_platform/analytics/impact/arl_delta.py            ARL0 before and after
src/spc_platform/domain/change_request.py
src/spc_platform/domain/baseline_version.py               versioning and supersession
src/spc_platform/domain/approval.py
src/spc_platform/application/use_cases/simulate_change.py
src/spc_platform/application/use_cases/qualify_baseline.py
src/spc_platform/application/use_cases/approve_baseline.py
src/spc_platform/application/ports/change_request_repository.py
src/spc_platform/infrastructure/repositories/change_request_repository.py
configs/spc/baseline_qualification.yaml
```

## Testing requirements

| Tier | What it must establish |
|---|---|
| `unit/` | Approval without an impact statement raises. Approval by an unauthorised actor raises. A superseded baseline is retained and a historical violation still resolves to the limits in force when it was raised (AC-D1). |
| `unit/` | No production writer accepts a simulated result. A structural test, because the consequence of this leaking is a fabricated baseline in the audited path. |
| `statistical/` | A rule set change of known ARL impact produces the expected before-and-after figures, verified against the theoretical values used in Module 3's ARL tests rather than against the implementation's own prior output. |
| `unit/` | Baseline qualification excludes configured engineering-time intervals, and refuses rather than qualifying a window that includes them. |
| `contract/` | A replay repeated with the same data, code, and configuration revisions returns an identical result (FR-CC06). |
| `e2e/` | Propose a baseline, simulate, approve, and confirm charts move to the new limits while historical violations remain explainable. |

## Documentation required

- `docs/api/change-control.md` — the change request lifecycle and the impact
  contract.
- `docs/quality/change-control.md` — which change types require which evidence,
  extending the change control table in
  [QUALITY_ASSURANCE_PLAN.md](../QUALITY_ASSURANCE_PLAN.md) §6.
- `docs/runbooks/baseline-recalculation.md` — the procedure a quality engineer
  follows, including what to do when no window qualifies.
- A PRD amendment adding FR-CC01 – FR-CC06 before implementation begins.

## Future extension points

- **Detector A/B comparison** — two registered detectors replayed over the same
  history, using the same delta machinery.
- **Batch change proposals** — a rule set revision across many parameters, with
  one aggregated impact statement.
- **Scheduled baseline review** — periodic qualification proposals raised
  automatically, still requiring human approval.
- **Sampling plan simulation** — what detection performance would look like at a
  different sampling frequency, which is a genuine engineering question and a
  natural extension of replay.
- **What-if on specification changes** — capability impact across affected
  products before a customer commitment.

---

**Related:** [MODULE_DESIGN.md](../MODULE_DESIGN.md) ·
[03-spc-engine.md](03-spc-engine.md) ·
[10-utilities-and-configuration.md](10-utilities-and-configuration.md) ·
[QUALITY_ASSURANCE_PLAN.md](../QUALITY_ASSURANCE_PLAN.md)
