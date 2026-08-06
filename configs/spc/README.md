# SPC configuration

Chart-type defaults and named run-rule sets. Per-parameter selection lives in
the control plan (`data/reference/control_plans.yaml`); this directory holds
the named sets a plan may reference.

| File | Contents |
|---|---|
| `charts.yaml` | Default sigma multiplier, EWMA λ, CUSUM k/h, R-to-S switchover |
| `rule_sets.yaml` | Western Electric, Nelson, and Shewhart-only sets with severities |

Rule identities must match `src/spc_platform/analytics/rules/catalogue.py`. An
unknown identity is a configuration error at evaluation time — an unpublished
rule has no measured ARL₀ (FR-R06).

Changing a default or a rule definition is a statistical behaviour change and
requires an ADR plus a changelog entry marked **[STAT]**.
