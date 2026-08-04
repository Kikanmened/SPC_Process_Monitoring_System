# Module 9 — Dashboard and Reporting

**Owning layers:** `dashboard/`, `application/views/`, `infrastructure/reporting/`, `infrastructure/notifications/`
**Depends on:** Modules 3, 4, 5, 6, 7, 8, 10
**Depended on by:** nothing — presentation is always a leaf
**Requirement coverage:** FR-S01, FR-S03 – FR-S06, FR-A01, FR-A05, FR-A06, FR-RP01 – FR-RP05; NFR-P03, NFR-P04, NFR-U01 – NFR-U06
**Delivered in:** Phase 12 (screens), Phase 13 (reports and packages) · **Status:** Design — not implemented

---

## Purpose

Put the right result in front of the right person, in a form they can act on and
later defend.

The design priority is settled: **the shift lead's question is answered first**,
because it is asked most often and under the most pressure, sometimes at 03:00.
"Is this normal, and if not, what do I do?" must be answerable within one screen
(NFR-U01). A screen that takes three clicks to reveal whether a point violated a
rule has failed that user regardless of how well it serves anyone else.

The module's hard constraint is that it contains **no computation**. Every number
displayed or printed comes from a use case. A dashboard that computes is a
second, unverified implementation of the analytics engine, and the two will
diverge — at which point the audited number and the displayed number disagree
and neither can be trusted.

## Responsibilities

- Render the screens: line overview ordered by what needs attention, control
  chart viewer with violation markers and point drill-down, capability, MSA,
  tool and chamber comparison, wafer map, and the alarm queue.
- Present the open violation queue ordered by severity and age, with the OCAP
  reference visible on every alarm (FR-A01, FR-A04 display, AC-B2).
- Render specification and control limits **visually distinctly**, and never
  interchangeably (FR-C06 display, NFR-U02).
- Signal out-of-control state by shape and label, never by colour alone
  (NFR-U03).
- Show sample size and time window beside every displayed statistic (NFR-U04),
  and state an uncomputable result as such rather than inventing a value
  (NFR-U05).
- Render wafer maps at true site coordinates in millimetres from wafer centre
  (FR-S01), with fixed colour scale limits across any comparison set, displayed
  numerically (FR-S03), using only perceptually uniform, colour-vision-safe
  scales (FR-S04), with site-level drill-down (FR-S05), degrading above the
  point budget to an aggregated view that says on screen that it has done so
  (FR-S06).
- Generate the four report types with a provenance header on every artefact, and
  regenerate any report deterministically from its revisions (FR-RP01 – FR-RP03).
- Assemble self-contained audit packages: charts, data extract, limits in force
  at the time, configuration revision, and disposition records (FR-RP04).
- Dispatch **digested** notifications, never one per violation, and escalate
  unacknowledged violations after the configured interval (FR-A05, FR-A06).
- Invalidate cached views when the data or configuration revision changes
  (NFR-U06).

**Not this module's work:** any statistic, any limit, any judgement of
significance, and any decision about what a result means.

## Public interfaces

The dashboard consumes view models produced by the application layer. The view
model is the contract; Streamlit is an implementation detail behind it.

```python
def build_chart_view(request: ChartViewRequest) -> ChartView:
    """Points, limits, zones, violations, and equipment state markers, ready to render."""


def build_wafer_map_view(request: WaferMapRequest) -> WaferMapView:
    """One computation behind both the interactive figure and the static export."""


class ReportRenderer(Protocol):
    def render(self, report: ReportModel, target: RenderTarget) -> ReportArtefact: ...


class Notifier(Protocol):
    def dispatch(self, digest: NotificationDigest) -> DispatchReceipt: ...
```

`WaferMapView` is the seam required by [ADR-0018](../DECISION_LOG.md#adr-0018):
the interactive figure and the static report export are two renderings of one
computation and therefore cannot disagree. Colour scale limits are a property of
the view, not of either renderer.

| Exception | Raised when |
|---|---|
| `ViewDataUnavailableError` | The use case declined; the reason is rendered, not swallowed |
| `RenderBudgetExceededError` | Handled internally by labelled degradation, never by silent downsampling |
| `NotificationDispatchError` | The transport failed; recorded and surfaced, never dropped |

## Dependencies

| Depends on | For |
|---|---|
| Modules 3, 4, 5, 6, 7, 8 | Every number displayed, through their use cases only |
| Module 10 | Theme and display configuration, provenance for headers, audit of report generation and data access |
| Streamlit, Plotly | Interactive presentation; confined to `dashboard/` |
| Jinja2, WeasyPrint, Matplotlib | Deterministic HTML-to-PDF report rendering |

The dashboard imports application use cases and nothing deeper. It never imports
`analytics/`.

## Expected inputs

| Input | Source | Notes |
|---|---|---|
| View requests | User interaction, scheduler | Parameter, window, filters, comparison set |
| Results | Modules 3 – 8 | Already qualified with n, window, estimator, provenance |
| Refusals | Modules 3, 4 | Rendered as stated reasons, with equal prominence to results |
| Theme and display policy | `configs/base/` | Limit styling, colour scales, point budget |
| Notification policy | `configs/alerting/` | Digest interval, escalation interval, recipients by role |

## Expected outputs

| Output | Destination | Contents |
|---|---|---|
| Rendered screens | Browser | Charts, queues, wafer maps, comparisons, with n and window everywhere |
| Report artefacts | `reports/generated/` | HTML and PDF with a provenance header: data, code, and configuration revision, generation timestamp, parameters used |
| Audit package | `reports/generated/` | Self-contained and independently verifiable by its recipient |
| Notification digests | Notification relay | Grouped by recipient and interval, with escalation state |
| Audit records | `logs/audit/` | Report generation and measurement data access (FR-AU03, NFR-SE05) |

## Files to create

```
dashboard/app/main.py
dashboard/pages/01_line_overview.py
dashboard/pages/02_control_chart.py
dashboard/pages/03_capability.py
dashboard/pages/04_msa.py
dashboard/pages/05_wafer_map.py
dashboard/pages/06_tool_comparison.py
dashboard/pages/07_alarm_queue.py
dashboard/pages/08_trends.py
dashboard/components/chart_figure.py
dashboard/components/wafer_map_figure.py
dashboard/components/statistic_label.py            enforces n and window beside every value
dashboard/components/refusal_panel.py
dashboard/state/caching.py                         keyed on data and config revision
dashboard/theme/limits.py                          spec versus control limit styling
dashboard/theme/colour_scales.py                   perceptually uniform only
src/spc_platform/domain/wafer_map_view.py
src/spc_platform/application/views/chart_view.py
src/spc_platform/application/views/wafer_map_view_builder.py
src/spc_platform/application/views/queue_view.py
src/spc_platform/application/use_cases/generate_report.py
src/spc_platform/application/use_cases/assemble_audit_package.py
src/spc_platform/application/use_cases/dispatch_notifications.py
src/spc_platform/application/ports/notifier.py
src/spc_platform/application/ports/report_renderer.py
src/spc_platform/infrastructure/reporting/html_renderer.py
src/spc_platform/infrastructure/reporting/templates/spc_summary.html.j2
src/spc_platform/infrastructure/reporting/templates/capability_study.html.j2
src/spc_platform/infrastructure/reporting/templates/msa_report.html.j2
src/spc_platform/infrastructure/reporting/templates/excursion_summary.html.j2
src/spc_platform/infrastructure/notifications/smtp_notifier.py
configs/alerting/notifications.yaml
```

## Testing requirements

| Tier | What it must establish |
|---|---|
| `unit/` | Zero statistical computation in `dashboard/` — enforced by `import-linter` denying `analytics` imports, and by review. Every displayed statistic renders with n and window; the component makes omission impossible. |
| `contract/` | A report regenerates identically from the same data, code, and configuration revisions (FR-RP03). The provenance header is present on every artefact type. |
| `unit/` | The same `WaferMapView` produces the interactive figure and the static export, asserted by comparing the data each describes (Phase 12 exit criterion). |
| `unit/` | Colour scale limits are identical across a comparison set, and per-wafer autoscaling occurs only when explicitly requested and labelled (AC-S3, R-43). |
| `performance/` | Chart load under 1 s warm (NFR-P03); wafer map within budget at 5 000 markers, with degradation above it (NFR-P04). |
| `e2e/` | Violation appears in the queue with its OCAP, is acknowledged, dispositioned, and appears correctly in the generated excursion summary. |

Exact pixel output is deliberately not tested. Chart *data* is asserted;
appearance is reviewed by a human ([TESTING_STRATEGY.md](../TESTING_STRATEGY.md) §7).

## Documentation required

- `docs/api/views.md` — the view model contracts.
- `docs/quality/report-provenance.md` — what the provenance header contains and
  how a recipient verifies a report independently.
- `docs/onboarding/` — a screen-by-screen guide written for the shift lead, not
  for a developer.
- `docs/runbooks/report-regeneration.md`.
- Accessibility notes with the theme: shape and label signalling, colour-vision
  safety, and the reasoning behind both.

## Future extension points

- **Alternative front end** — the view model contract is the seam; replacing
  Streamlit touches no use case ([SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) §1).
- **Additional report types** — a template plus a report model.
- **Additional notification transports** — one port, already contract-tested.
- **Additional wafer map overlays** — defect maps and deviation-from-target,
  behind the same `WaferMapView`.
- **Role-tailored landing screens** per persona, once authorisation roles are
  in place (NFR-SE04).
- **Export to customer-specific formats** for PPAP submissions.

---

**Related:** [MODULE_DESIGN.md](../MODULE_DESIGN.md) ·
[07-root-cause-analysis.md](07-root-cause-analysis.md) ·
[ADR-0018](../DECISION_LOG.md#adr-0018) ·
[PRODUCT_REQUIREMENTS.md](../PRODUCT_REQUIREMENTS.md)
