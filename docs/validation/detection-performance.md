# Detection Performance Scorecard

**Status:** Measured · Phase 9
**Last updated:** 2026-08-05
**Authority:** [TESTING_STRATEGY.md](../TESTING_STRATEGY.md) §3.5

The platform's central claim is that detection performance is *measured*, not
asserted. Every figure below comes from a seeded statistical test; none is a
snapshot of current output frozen as an expectation.

## 1. In-control average run length

Source: `tests/statistical/analytics/test_arl.py`

| Rule set | Theoretical ARL₀ | Tolerance | Result |
|---|---|---|---|
| Shewhart 3σ alone (WE-1) | 370.4 | ±15% | Pass |
| Western Electric 1–4 | 91.75 | ±15% | Pass |
| Nelson 1–8 | (simulated reference) | ±15% | Pass |

References: Montgomery (2019) §5.3.2–5.3.3; Champ and Woodall (1987).

## 2. Detection power against known step shifts

Source: `tests/statistical/analytics/test_detection_power.py`

Method: 200 independent individuals charts. Phase I limits estimated on 50
pre-onset points; Western Electric rules 1–4 evaluated on the full series;
scored by `analytics/scoring` against the known onset. Seed `20260805`.

| Shift | Detection rate | Acceptance | Localisation (≤3 pts) | Acceptance | Mean latency |
|---|---|---|---|---|---|
| 1.5σ | 1.00 | ≥ 0.95 | 0.52 | n/a† | 4.1 points |
| 3.0σ | 1.00 | ≥ 0.99 | 0.99 | ≥ 0.80 | 0.8 points |

† At 1.5σ a Shewhart chart's ARL₁ is about fifteen points, so most detections
fall outside a ±3 window by construction. The localisation claim is asserted
at 3σ, where the chart is designed to catch the shift on contact.

Pre-onset false alarms across the 200 trials sit near the Western Electric
rate implied by ARL₀ ≈ 91.75 (precise ARL₀ is the table above).

## 3. Spatial signature classification

Source: `tests/statistical/analytics/test_spatial.py`

Method: thirteen-site wafers with generator-imposed signatures; classifier in
`analytics/spatial` uses geometric predictors that do **not** share code with
the generator (ADR-0021).

| Signature | Clean recovery | Noisy recovery (≥45/50) | False-positive budget on noise |
|---|---|---|---|
| Radial | Pass | Pass | — |
| Edge | Pass | Pass | — |
| Asymmetric | Pass | Pass | — |
| None | Pass | Pass | ≤ 5% (measured ~1% on plan 13) |

## 4. Scoring harness integrity

Source: `tests/statistical/analytics/test_detection_scoring.py`

The scorecard arithmetic — rate, latency, localisation, false-alarm rate — is
verified on hand-counted cases before it is trusted to score the engine. A
wrong harness cannot flatter a wrong engine.

## 5. What this document is not

- It is not a tune-then-score loop. Thresholds were set from published theory
  and geometric reasoning; the numbers above are the measurement, not the
  target the code was fitted to.
- It does not activate detectors in production. Detector registries and
  activation gates are proposed requirements (FR-AD01 – FR-AD04) and are not
  implemented.
- It is not evidence about real fab data. The synthetic generator is the
  instrument that makes these measurements possible (ADR-0021).

---

**Related:** [TESTING_STRATEGY.md](../TESTING_STRATEGY.md) ·
[DATASET_GUIDE.md](../DATASET_GUIDE.md) ·
[modules/06-anomaly-detection.md](../modules/06-anomaly-detection.md)
