<!--
The checklist is the reviewer checklist from QUALITY_ASSURANCE_PLAN.md §5.
Delete a section only when it genuinely does not apply, and say why.
-->

## What this changes, and why

<!-- The problem, not the diff. A reviewer should understand the change
     before reading a line of it. -->

## Requirement, risk, and phase

- Requirements: <!-- FR-…, NFR-… — or "none", if this changes no behaviour -->
- Risks affected: <!-- R-… from docs/RISK_REGISTER.md, or "none" -->
- Phase / milestone: <!-- e.g. Phase 7 · M7 -->

## Verification

<!-- What you ran, and what it showed. "Tests pass" is not evidence; name the
     tier and the behaviour asserted. -->

- [ ] `make check` passes locally
- [ ] New behaviour has a test that fails without this change
- [ ] Refusal paths are tested, not only success paths

## Statistical impact

<!-- Required for any change to analytics/, an estimator, a rule definition, a
     constant, or a chart. Delete this section only if none of those changed.

     A change to a sigma estimator or a rule definition retroactively alters
     the meaning of every historical number, which is why this statement is
     mandatory rather than encouraged (QUALITY_ASSURANCE_PLAN.md §6). -->

- Existing baselines invalidated: yes / no — <!-- which, and why -->
- Existing reports invalidated: yes / no — <!-- which, and why -->
- Historical comparisons affected: yes / no
- Reference source for every expected value: <!-- NIST/SEMATECH §…, Montgomery Example … -->
- Measured ARL₀ effect, if a rule set changed:

## Reviewer checklist

- [ ] Does it belong in this layer, and does it respect the dependency direction?
- [ ] Is every statistical estimator named explicitly — no parameter called `sigma`?
- [ ] Is every formula and constant cited, from a publicly obtainable source?
- [ ] Are units explicit at every boundary?
- [ ] Are there invented defaults, silent fallbacks, or swallowed exceptions?
- [ ] Do the tests assert against an external reference rather than snapshot
      current output?
- [ ] Are documentation and `.cursor/rules/` updated in this same pull request?
- [ ] Does this change invalidate baselines, reports, or historical
      comparisons — and does the description say so?

## Rollback

<!-- How to undo this if it turns out to be wrong, and what has to be
     re-checked afterwards — in particular, results produced while it was
     live. -->
