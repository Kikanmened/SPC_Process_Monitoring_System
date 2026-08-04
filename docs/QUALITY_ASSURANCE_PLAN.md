# Quality Assurance Plan

**Document owner:** Project lead
**Status:** Active
**Last updated:** 2026-08-03

This plan covers quality in two senses, and keeping them distinct matters.

**Product quality** — the software is correct, maintainable, and secure.
Covered by [TESTING_STRATEGY.md](TESTING_STRATEGY.md) and
[CODING_STANDARDS.md](CODING_STANDARDS.md), summarised here as gates.

**Quality-system fitness** — the platform is capable of functioning as a
component of a quality management system operating under IATF 16949. This is
the harder and more interesting requirement, and it is what distinguishes this
project from a charting library. Most of this document addresses it.

---

## 1. Quality objectives

| # | Objective | Measure | Target |
|---|---|---|---|
| Q1 | Statistical results are verifiably correct | Reference-validated cases passing | 100% |
| Q2 | Detection is effective | Detection rate for injected shifts ≥ 1.5σ | ≥ 95% |
| Q3 | False alarms are controlled | Measured ARL₀ vs. theoretical for the configured rule set | Within ±15% |
| Q4 | Every result is traceable | Outputs carrying data, code, and config revision | 100% |
| Q5 | Every consequential action is auditable | Actions with a complete audit record | 100% |
| Q6 | The codebase remains maintainable | Type coverage; architecture violations | 100%; zero |
| Q7 | No confidential or secret material is committed | Secret-scan findings | Zero |

Q2 and Q3 are stated as a pair deliberately. Either is trivial to achieve
alone — signal on everything, or signal on nothing. Only the pair describes a
system an engineer would trust.

## 2. Quality-system alignment

The platform is designed to *support* a quality management system, not to
certify one. The mapping below states which IATF 16949 / ISO 9001 expectations
it addresses and how.

| Requirement area | Expectation | How the platform addresses it |
|---|---|---|
| **Control plan** (IATF 8.5.1.1) | Each characteristic has a defined control method, sample size, frequency, and reaction plan | `data/reference/control_plans.yaml` is the source for chart selection and rule configuration; the platform implements the control plan rather than a parallel configuration |
| **SPC application** (AIAG SPC) | Correct chart selection, rational subgrouping, valid limits | Chart type per parameter class; subgrouping strategy recorded on every subgroup; limits derived only from a qualified baseline |
| **MSA** (IATF 7.1.5.1.1, AIAG MSA 4th ed.) | Measurement systems analysed for variation | Gauge R&R by ANOVA, bias, linearity, stability; %GRR and NDC reported with acceptance judgement |
| **Process capability** (IATF 9.1.1.1) | Capability demonstrated and maintained for identified characteristics | Cp/Cpk/Pp/Ppk/Cpm with mandatory stability precondition, stated estimator, sample size, and window |
| **Reaction plan** (IATF 8.5.1.1, 9.1.1.1) | Predefined action on out-of-control or non-capable output | Every alarm links to its OCAP; disposition is required to close |
| **Non-conforming output** (ISO 9001 8.7) | Identification, containment, disposition, records | Excursion workflow with disposition states and mandatory reason |
| **Corrective action** (ISO 9001 10.2) | Root cause analysis and effectiveness verification | Excursions link to 8D/CAPA references; recurrence is measurable from history |
| **Traceability** (IATF 8.5.2.1) | Product history reconstructable | Every measurement carries lot, wafer, slot, tool, chamber, recipe, and metrology tool |
| **Records and data integrity** (ISO 9001 7.5, ALCOA+) | Records attributable, legible, contemporaneous, original, accurate | Append-only audit trail with actor, timestamp, before/after, reason |
| **Change control** | Changes reviewed, approved, recorded | Limits, spec limits, and rule sets change only through reviewed pull requests; baselines are versioned with approver and effective date |

### 2.1 Data integrity (ALCOA+)

The principle behind the audit design, stated explicitly because it is what
auditors actually test:

| Principle | Implementation |
|---|---|
| **Attributable** | Every audit record names the actor — a person or a named system process |
| **Legible** | Structured JSON with a documented schema; human-readable rendering in the UI |
| **Contemporaneous** | Records are written at the moment of the action, with timezone-aware timestamps |
| **Original** | `raw/` is immutable; superseded measurements are marked, never deleted |
| **Accurate** | Schema validation at every boundary; no silent coercion |
| **Complete** | All consequential actions recorded, including refusals and failed attempts |
| **Consistent** | Single canonical vocabulary ([GLOSSARY.md](GLOSSARY.md)); one timestamp standard |
| **Enduring** | Append-only storage, exported to durable retention |
| **Available** | Queryable through the API for the retention period |

### 2.2 Auditable events

The platform records, at minimum:

- Control limit change: old value, new value, baseline reference, approver,
  reason, effective date
- Baseline creation, approval, and supersession
- Specification limit change (via reviewed configuration change)
- Violation raised, acknowledged, dispositioned — with actor and reason
- Rule set or chart type configuration change
- Report generation, with the exact data/code/config revisions used
- Data pipeline run: inputs, outputs, validation results, failures
- Access to measurement data through the API

## 3. Product quality gates

| Gate | Check | Blocking | When |
|---|---|---|---|
| G1 | Ruff format and lint | Yes | Pre-commit, CI |
| G2 | `mypy --strict` | Yes | Pre-commit, CI |
| G3 | Architecture rules (`import-linter`) | Yes | CI |
| G4 | Unit tests | Yes | Pre-commit, CI |
| G5 | **Statistical validation** | Yes | Pre-commit, CI (separate stage) |
| G6 | Contract tests | Yes | CI |
| G7 | Integration tests | Yes | CI |
| G8 | End-to-end tests | Yes | CI |
| G9 | Performance budgets | Yes (on regression) | CI |
| G10 | Security: `bandit`, `pip-audit`, `gitleaks` | Yes | CI, weekly schedule |
| G11 | Coverage non-regression in `domain/` and `analytics/` | Yes | CI |
| G12 | Documentation currency | Review | Pull request |

**G5 is reported as its own CI stage.** A failure there means a number the
platform produces is wrong, and that must be unmistakable rather than buried
among hundreds of passing unit tests.

## 4. Statistical validation approach

Detail in [TESTING_STRATEGY.md](TESTING_STRATEGY.md) §3. The evidence chain, in
short:

1. **External references** — NIST/SEMATECH and Montgomery, exclusively, per the
   three-layer hierarchy in [ADR-0017](DECISION_LOG.md#adr-0017). Every expected
   value cites its source, and every source is publicly obtainable. AIAG and
   SEMI publications govern terminology, acceptance bands, and interface
   conventions but never supply a numerical expectation.
2. **Hand computation** — worked in the test docstring so a reviewer verifies
   without executing.
3. **Analytical invariants** — properties that must hold for all inputs
   (Cp ≥ Cpk; scale/shift equivariance; EWMA λ=1 ≡ individuals).
4. **Simulation** — measured ARL₀ against theory, so false-alarm behaviour is
   quantified rather than assumed.
5. **Ground-truth scoring** — detection rate, latency, and localisation against
   known injected faults.

Results are recorded in `docs/validation/` so the question "how do you know
your Cpk is right?" has a documentary answer, not a verbal one.

## 5. Review process

**Every change is reviewed** — including AI-generated changes, which are
reviewed more carefully rather than less. The characteristic failure mode of
generated code in this domain is a plausible-looking statistical constant or a
helpfully added fallback default, and both pass casual reading.

Reviewer checklist:

- [ ] Does it belong in this layer? Does it respect the dependency direction?
- [ ] Is every statistical estimator named explicitly?
- [ ] Is every formula and constant cited?
- [ ] Are units explicit at every boundary?
- [ ] Are there invented defaults, silent fallbacks, or swallowed exceptions?
- [ ] Do the tests assert behaviour against an external reference, or merely
      snapshot current output?
- [ ] Are refusal paths tested as well as success paths?
- [ ] Does this change invalidate existing baselines, reports, or historical
      comparisons — and does the PR say so?
- [ ] Are documentation and `.cursor/rules/` updated in this same PR?

## 6. Change control

| Change type | Route | Additional requirement |
|---|---|---|
| Code | Pull request, all gates green | — |
| **Statistical behaviour** | Pull request marked `stat:` | Reference-validated test; explicit impact statement on existing baselines and reports |
| Specification limit | Configuration PR | Effective date; historical values retained |
| Control limit / baseline | Application workflow, not a code change | Approver recorded; superseded baseline retained |
| Rule set | Configuration PR | Measured ARL₀ impact stated |
| Schema | Migration + contract test update | Backward compatibility assessed |
| Dependency | Pull request | Justification, licence check, security scan |

A change to a sigma estimator or a rule definition **retroactively alters the
meaning of every historical number**. That is why the impact statement is
mandatory rather than encouraged.

## 7. Defect management

| Severity | Definition | Response |
|---|---|---|
| **S1 — Critical** | Produces an incorrect statistical result, or loses audit data | Stop work. Fix, regression test, and assess every result produced since introduction. |
| **S2 — Major** | Missed detection or excessive false alarms | Fix in the current iteration; quantify the effect on measured ARL |
| **S3 — Moderate** | Functional defect with a workaround | Scheduled |
| **S4 — Minor** | Cosmetic or documentation | Backlog |

S1 carries an obligation absent from ordinary software: **assessing results
already produced.** If a limit calculation was wrong for three weeks, every
report generated in that window is suspect, and identifying them is part of the
fix — which is only possible because every output records its code revision.

Every defect fix requires a regression test verified to fail against the old
code.

## 8. Documentation quality

- Documentation updates in the same pull request as the change.
- Every architectural decision recorded in [DECISION_LOG.md](DECISION_LOG.md)
  with the options rejected.
- Formulae cite sources.
- Glossary terms used consistently across code, configuration, UI, and prose.
- Internal links verified in CI; a broken cross-reference is a defect.

## 9. Continuous improvement

Reviewed at the end of each phase:

- Defects found after merge, by category — each one indicates a missing gate
- Measured ARL₀ drift as rule configurations evolve
- Statistical validation coverage against the reference set
- Recurring AI-agent errors, each of which becomes a `.cursor/rules/` entry
  rather than a repeated correction

The last point is the project's own corrective-action loop: a mistake that
recurs is a process failure, not an incident, and it is fixed once at the
source.

---

**Related:** [TESTING_STRATEGY.md](TESTING_STRATEGY.md) ·
[CODING_STANDARDS.md](CODING_STANDARDS.md) ·
[RISK_REGISTER.md](RISK_REGISTER.md) ·
[GLOSSARY.md](GLOSSARY.md)
