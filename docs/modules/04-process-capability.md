# Module 4 — Process Capability Analysis

**Owning layers:** `analytics/capability/`, `analytics/msa/`, `analytics/distribution/`, `application/`
**Depends on:** Modules 2, 3, 10
**Depended on by:** Modules 5, 8, 9
**Requirement coverage:** FR-P01 – FR-P09, FR-M01 – FR-M06; NFR-U04, NFR-C01
**Delivered in:** Phase 9 (analytics), Phase 11 (use cases) · **Status:** Design — not implemented

---

## Purpose

Answer the question a customer or auditor actually asks: can this process meet
its specification, and is the measurement system good enough for the answer to
mean anything?

Both halves are here deliberately. Measurement system analysis is not a separate
concern from capability — it is the precondition for it. If gauge R&R consumes
40% of the tolerance, the control chart is substantially plotting the
measurement system rather than the process, and a Cpk computed from that data
describes an artefact. The two share the tolerance and estimator machinery and
are reported together.

This module also owns the platform's most important refusal. A capability index
computed on a process that is not demonstrated to be in control is a confident
number describing a distribution that does not exist, and it is exactly the sort
of evidence that fails an audit (R-08, AC-C2).

## Responsibilities

- Compute Cp, Cpk, Pp, and Ppk (FR-P01), and Cpm (FR-P02).
- Name the sigma estimator on every result and in every signature. There is no
  parameter called `sigma`; `cpk` takes `sigma_within`, `ppk` takes
  `sigma_overall`, and the caller must choose (FR-P03,
  [CODING_STANDARDS.md](../CODING_STANDARDS.md) §1.1).
- Handle single-sided specifications correctly rather than substituting an
  infinite bound (FR-P08).
- Assess normality and record the assessment with the result (FR-P06).
- Support non-normal capability by transformation (Box-Cox, Johnson) or the
  percentile method, recording which was used (FR-P07).
- Report sample size, time window, estimator, and stability status alongside
  every index — all four, always (FR-P09, NFR-U04, AC-C1).
- Compute gauge R&R by the ANOVA method, reporting %GRR of tolerance, %GRR of
  total variation, and NDC (FR-M01, FR-M02).
- Apply configured acceptance bands and state an acceptability judgement
  (FR-M03). The bands are configuration, aligned to AIAG conventions but never
  reproduced from the publication ([ADR-0017](../DECISION_LOG.md#adr-0017)).
- Compute bias, linearity, and stability (FR-M04); link every measurement to its
  metrology tool (FR-M05); flag an unqualified or expired gauge study (FR-M06).
- **Refuse** — as application policy — to produce a capability result for a
  process not demonstrated to be in control (FR-P04), or below the configured
  minimum sample size (FR-P05).

Gauge qualification status travels with every capability result. Whether an
unqualified gauge *blocks* the result is a policy question the current
requirement set does not settle; the design keeps it configurable and defaults
to reporting the status prominently rather than refusing.

## Public interfaces

```python
def cp(usl: float, lsl: float, sigma_within: float) -> float: ...
def cpk(mean: float, usl: float | None, lsl: float | None, sigma_within: float) -> float: ...
def pp(usl: float, lsl: float, sigma_overall: float) -> float: ...
def ppk(mean: float, usl: float | None, lsl: float | None, sigma_overall: float) -> float: ...
def cpm(mean: float, target: float, usl: float, lsl: float, sigma_overall: float) -> float: ...


def assess_normality(values: FloatArray) -> NormalityAssessment:
    """Test statistic, p-value, and the test used. Never a bare boolean."""


def gauge_rr_anova(study: GaugeStudyData, tolerance: Tolerance) -> GaugeRRResult:
    """%GRR of tolerance and of total variation, NDC, and variance components."""
```

Every function above carries a NumPy-style docstring with **Parameters** (units
and constraints), **Returns**, **Raises**, and **References** citing
NIST/SEMATECH or Montgomery.

| Exception | Raised when |
|---|---|
| `UnstableProcessError` | Open violations exist in the requested window (FR-P04) |
| `InsufficientDataError` | Below the configured minimum n; carries n and required n |
| `MissingSpecificationError` | No specification limit in force for the window; never assumed |
| `NonNormalWithoutMethodError` | Normality is rejected and no transformation method is configured |
| `DegenerateSeriesError` | Zero variation makes an index undefined; never returns `inf` |

## Dependencies

| Depends on | For |
|---|---|
| Module 2 | The measurement series and its window |
| Module 3 | Stability evidence — the violation set in the window and the σ̂_within estimate consistent with the chart |
| Module 10 | Acceptance bands, minimum-n policy, spec limit effective dating, provenance, audit |
| `domain/` | `SpecificationLimit`, `CapabilityResult`, `GaugeStudy`, `Tolerance` |
| NumPy, SciPy, statsmodels | Distributions, Box-Cox, percentile methods, ANOVA variance components |

`SpecificationLimit` enters this module and `ControlLimit` does not. Capability
is measured against the customer requirement; stability is judged against the
process-derived boundary. Conflating them is the error the type system prevents.

## Expected inputs

| Input | Source | Notes |
|---|---|---|
| Measurement series and window | Module 2 | Timezone-aware bounds |
| Stability evidence | Module 3 | Violations in the window; the estimator used for σ̂_within |
| Specification limits | `data/reference/specification_limits.yaml` | With effective dates; historical values retained (FR-CF03) |
| Capability policy | `configs/spc/` | Minimum n, transformation preference, refusal behaviour |
| Gauge study data | Processed zone | Operators, parts, trials, metrology tool identity |
| MSA acceptance bands | `configs/base/` | Configured, not hard-coded |

## Expected outputs

| Output | Consumer | Contents |
|---|---|---|
| `CapabilityResult` | Modules 5, 8, 9 | Indices, estimator name, n, window, stability status, normality assessment, transformation method, spec limits used with effective date, gauge status, provenance |
| `GaugeRRResult` | Modules 5, 9 | %GRR of tolerance and of total variation, NDC, variance components, acceptability judgement, study date and expiry |
| `CapabilityRefusal` | Module 9 | The reason a result was declined, in terms an engineer can act on |

A refusal is a first-class output, rendered as a stated reason rather than an
empty chart. "The interface never invents a value; an uncomputable result is
stated as such" (NFR-U05).

## Files to create

```
src/spc_platform/analytics/capability/__init__.py
src/spc_platform/analytics/capability/indices.py         cp, cpk, pp, ppk, cpm
src/spc_platform/analytics/capability/single_sided.py
src/spc_platform/analytics/capability/non_normal.py      transformation, percentile method
src/spc_platform/analytics/distribution/__init__.py
src/spc_platform/analytics/distribution/normality.py
src/spc_platform/analytics/distribution/transforms.py    Box-Cox, Johnson
src/spc_platform/analytics/msa/__init__.py
src/spc_platform/analytics/msa/gauge_rr.py               ANOVA method
src/spc_platform/analytics/msa/bias_linearity.py
src/spc_platform/analytics/msa/stability.py
src/spc_platform/analytics/msa/acceptance.py             configured bands, judgement
src/spc_platform/domain/specification_limit.py
src/spc_platform/domain/capability_result.py
src/spc_platform/domain/gauge_study.py
src/spc_platform/application/use_cases/generate_capability_report.py
src/spc_platform/application/use_cases/run_gauge_study.py
src/spc_platform/application/ports/specification_repository.py
configs/base/msa_acceptance.yaml
configs/spc/capability.yaml
```

## Testing requirements

| Tier | What it must establish |
|---|---|
| `statistical/` | Every index reproduces a published worked example from NIST/SEMATECH or Montgomery, cited to example number. Gauge R&R by ANOVA reproduces a published study with its variance components, not only the headline %GRR. |
| `statistical/` (invariants) | Under Hypothesis: `Cp >= Cpk` for every input, without exception — if this ever fails, one of the two is wrong regardless of what the reference tables say. Indices are invariant under a consistent change of unit. A centred process gives `Cpk == Cp`. |
| `statistical/` (hand-computed) | Single-sided specification cases, which textbooks tabulate inconsistently. |
| `unit/` | The refusal paths: unstable process, insufficient n, missing specification, non-normal with no configured method. Each raises its own type with context. |
| `contract/` | Every `CapabilityResult` carries estimator, n, window, and stability status. The test fails if any of the four is absent, in the API response and in the report (AC-C1). |
| `e2e/` | A parameter with an open violation in the window yields a stated refusal and no index anywhere in the output (AC-C2). |

## Documentation required

- `docs/api/capability.md` and `docs/api/msa.md` — contracts, units,
  preconditions, exceptions, and references.
- `docs/quality/capability-method.md` — which index answers which question, why
  the estimator must be stated, and how non-normal cases are handled. The
  document a quality engineer cites when a customer challenges a number.
- `docs/validation/` — reference case results for indices and gauge R&R.
- An ADR if the default sigma estimator or the stability precondition changes.

## Future extension points

- **Additional capability indices** — Cpkm and confidence intervals on indices,
  both additive to the result object.
- **Attribute capability** — defect rates and PPM against the same reporting
  contract.
- **Additional non-normal methods** — the method is recorded on the result, so a
  new one is a registration rather than a change of contract.
- **Gauge study scheduling** — expiry is already modelled; automated
  requalification prompts are a workflow addition (FR-M06).
- **Destructive and nested gauge studies** — a different variance model behind
  the same result type.

---

**Related:** [MODULE_DESIGN.md](../MODULE_DESIGN.md) ·
[03-spc-engine.md](03-spc-engine.md) ·
[09-dashboard-and-reporting.md](09-dashboard-and-reporting.md) ·
[QUALITY_ASSURANCE_PLAN.md](../QUALITY_ASSURANCE_PLAN.md)
