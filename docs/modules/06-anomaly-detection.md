# Module 6 — Anomaly Detection

**Owning layers:** `analytics/detectors/`, `analytics/spatial/`, `analytics/scoring/`, `application/`
**Depends on:** Modules 2, 3, 10
**Depended on by:** Modules 5, 7, 9
**Requirement coverage:** FR-S02; FR-R05, FR-D07 (flag semantics). **Proposed and not approved:** FR-AD01 – FR-AD04
**Delivered in:** Phase 8 (scoring inputs), Phase 9 (detectors and harness) · **Status:** Design — partially proposed scope

---

## Purpose

Own the contract that every detection source must satisfy, and the harness that
measures how well detection actually performs.

The framing matters. This project's central claim is not that it detects
anomalies — anything can raise a flag — but that **its detection performance is
measured rather than asserted**. Detection rate, latency, localisation, and
false-alarm rate are quantities here, available only because every fault in the
synthetic data has known ground truth. Module 6 is where that measurement lives.

Within this release the module delivers two things: the detector contract with
its registry, and spatial signature detection on wafer maps (FR-S02) as the one
in-scope detector that is not expressible as a Shewhart run rule. Run-rule
detection remains in Module 3 and simply implements the same contract.

### Scope status

Model-based detection — multivariate SPC, PCA monitoring, drift forecasting — is
**out of scope for this release** and gated behind Phase 15, deliberately
(PRD §6.3, R-10). The contract defined here is what a future model must satisfy
to enter, so that it augments the audited path rather than bypassing it.

The ground-truth scoring harness exists today only as a test obligation
([TESTING_STRATEGY.md](../TESTING_STRATEGY.md) §3.5). Making it a platform
capability requires the following, **proposed and not in the PRD**:

| Proposed | Requirement |
|---|---|
| FR-AD01 | Every detection source implements one detector contract, emitting a detection that names the detector, its version, and its evidence |
| FR-AD02 | Detectors are registered per parameter in configuration; an unregistered detector cannot produce a platform signal |
| FR-AD03 | A detector carries a measured false-alarm characteristic before it may be activated |
| FR-AD04 | Detection performance is scored against ground truth and published as a platform artefact, not only as a test result |

## Responsibilities

- Define the `Detector` contract and the `Detection` result that every source
  produces, including Module 3's run rules.
- Maintain the registry that binds detectors to parameters through
  configuration, so the active detection set for any parameter is declarative
  and auditable.
- Classify wafer spatial signatures as radial, edge, asymmetric, or **none**
  (FR-S02), reporting the statistic behind the classification.
- Score detections against a ground-truth manifest: detection rate, latency,
  localisation, and false-alarm rate.
- Publish the detection scorecard to `docs/validation/` with the dataset and
  code revisions it was produced from.
- Refuse to activate a detector with no measured false-alarm characteristic.

**Not this module's work:** deciding what a detection means, or what to do about
it. Interpretation is Module 7; presentation and notification are Module 9.

## Public interfaces

```python
class Detector(Protocol):
    """Every detection source in the platform, rule-based or otherwise."""

    identity: DetectorIdentity          # name and version, recorded on every detection

    def detect(self, window: DetectionWindow) -> Sequence[Detection]: ...
    def false_alarm_characteristic(self) -> FalseAlarmCharacteristic: ...


def classify_spatial_signature(
    field: WaferField,
    policy: SignaturePolicy,
) -> SignatureClassification:
    """Radial, edge, asymmetric, or none, with the statistic and threshold used."""


def score_detections(
    detections: Sequence[Detection],
    truth: GroundTruthManifest,
    policy: ScoringPolicy,
) -> DetectionScorecard:
    """Detection rate, latency, localisation, and false-alarm rate against known faults."""
```

`SignatureClassification` always permits `none`, and `none` is the default
outcome rather than the residual. A classifier that must choose among three
patterns will find one in noise, which is the detection-side analogue of the
rendering failure recorded as R-43.

| Exception | Raised when |
|---|---|
| `UnregisteredDetectorError` | A detection arrives from a detector not registered for the parameter |
| `UncharacterisedDetectorError` | Activation is attempted with no measured false-alarm characteristic |
| `GroundTruthMismatchError` | The manifest and the scored dataset revisions do not correspond |
| `InsufficientSitesError` | Too few sites for a spatial classification to be meaningful |

## Dependencies

| Depends on | For |
|---|---|
| Module 2 | Site-level measurements with true coordinates, and the series under test |
| Module 3 | The run-rule detector implementing the contract; measured ARL₀ as its false-alarm characteristic |
| Module 10 | Detector registry configuration, thresholds, provenance, audit |
| Synthetic generator (Phase 8) | The ground-truth manifest — an instrument, not an application dependency |
| NumPy, SciPy | Spatial statistics and scoring |

## Expected inputs

| Input | Source | Notes |
|---|---|---|
| Detection window | Modules 2, 3 | Series, plotted points, and limits for the window under test |
| Site coordinates | Module 2 | Millimetres from wafer centre; required for spatial work (FR-S01 semantics) |
| Detector registry | `configs/spc/detectors.yaml` | Active detectors per parameter, with thresholds |
| Ground-truth manifest | `data/synthetic/` | Fault type, magnitude, onset point, affected entity |
| Scoring policy | `configs/base/` | Localisation tolerance, latency definition, evaluation windows |

## Expected outputs

| Output | Consumer | Contents |
|---|---|---|
| `Detection[]` | Modules 7, 9 | Detector identity and version, point or region, severity, evidence, provenance |
| `SignatureClassification` | Modules 7, 9 | Class including `none`, statistic, threshold, sites used |
| `DetectionScorecard` | Module 5, `docs/validation/` | Detection rate by fault magnitude, latency, localisation, false-alarm rate, seeds, revisions |
| `FalseAlarmCharacteristic` | Module 8 | Per detector, the input to any change-impact statement |

## Files to create

```
src/spc_platform/analytics/detectors/__init__.py
src/spc_platform/analytics/detectors/base.py             Detector protocol, Detection
src/spc_platform/analytics/detectors/rule_based.py       adapter over Module 3 rule evaluation
src/spc_platform/analytics/spatial/__init__.py
src/spc_platform/analytics/spatial/field.py              site coordinates to a wafer field
src/spc_platform/analytics/spatial/radial.py
src/spc_platform/analytics/spatial/edge.py
src/spc_platform/analytics/spatial/asymmetry.py
src/spc_platform/analytics/spatial/signature.py          classification, including none
src/spc_platform/analytics/scoring/__init__.py
src/spc_platform/analytics/scoring/metrics.py            rate, latency, localisation
src/spc_platform/analytics/scoring/ground_truth.py       manifest comparison
src/spc_platform/domain/detection.py
src/spc_platform/application/detection/registry.py
src/spc_platform/application/use_cases/score_detection_performance.py
scripts/quality/score_detection.py                       produces docs/validation/ artefacts
configs/spc/detectors.yaml
```

## Testing requirements

| Tier | What it must establish |
|---|---|
| `contract/` | One detector suite that every detector passes, including the rule-based adapter: identity and version on every detection, no detection outside the requested window, deterministic under a fixed seed. |
| `statistical/` | Spatial classification recovers each configured signature from generated wafers where the signature is known by construction, and — the case that matters — returns `none` on wafers generated without one, at a false-positive rate within its stated threshold. |
| `statistical/` | The scoring harness itself is verified on a constructed case where detection rate, latency, and localisation are known by hand, so that a wrong scorecard cannot flatter a wrong engine. |
| `unit/` | An unregistered or uncharacterised detector cannot produce a platform signal. |
| `e2e/` | A fault injected by the generator is detected, scored, and appears in the scorecard with the correct onset relationship. |

The scorecard must never be produced from the same run that tuned a threshold.
Tuning and scoring use separate generated datasets with separate seeds.

## Documentation required

- `docs/api/detection.md` — the detector contract, in enough detail that a
  future model author can satisfy it without reading the implementation.
- `docs/validation/detection-performance.md` — the published scorecard, with
  dataset revision, seeds, and the generator configuration used.
- `docs/quality/spatial-signatures.md` — what each signature means physically,
  and why `none` is the default classification.
- An ADR before any model-based detector is admitted, recording its assumptions,
  its degradation modes, and when it must **not** be used.

## Future extension points

- **Multivariate SPC** (Hotelling T², PCA) — implements `Detector`, gated behind
  Phase 15.
- **Drift forecasting** — same contract, scored on detection lead time, with a
  model card.
- **Additional spatial signatures** — swirl, striation, and hot-spot patterns
  behind the same classification contract with `none` preserved.
- **Cross-parameter and cross-tool anomaly detection** — a wider detection
  window, unchanged contract.
- **Detector A/B evaluation** — two registered detectors scored on the same
  ground truth; the comparison machinery is Module 8's.

---

**Related:** [MODULE_DESIGN.md](../MODULE_DESIGN.md) ·
[03-spc-engine.md](03-spc-engine.md) ·
[07-root-cause-analysis.md](07-root-cause-analysis.md) ·
[DATASET_GUIDE.md](../DATASET_GUIDE.md)
