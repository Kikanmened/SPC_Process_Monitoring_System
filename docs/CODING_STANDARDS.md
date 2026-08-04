# Coding Standards

**Document owner:** Project lead
**Status:** Active — binding on all code, human- or agent-written
**Last updated:** 2026-08-03

These standards exist because this codebase produces numbers that people act
on. A style guide for a web application optimises for readability; this one
optimises for **the impossibility of a silent numerical error**.

Rules marked **[ENFORCED]** are checked mechanically and fail the build. The
rest are review criteria. Where a rule seems pedantic, the rationale states the
failure it prevents — none of them are hypothetical.

---

## 1. Non-negotiable rules

The five that matter more than everything else in this document.

### 1.1 Name the estimator. Always.

There is no parameter called `sigma` anywhere in this codebase.

```python
# WRONG — the caller cannot know which sigma this wants, and both are plausible
def cpk(mean: float, sigma: float, usl: float, lsl: float) -> float: ...

# RIGHT — the caller must decide, and the reader can see the decision
def cpk(mean: float, sigma_within: float, usl: float, lsl: float) -> float: ...
def ppk(mean: float, sigma_overall: float, usl: float, lsl: float) -> float: ...
```

**Failure prevented:** Cpk computed from overall sigma. The label claims
short-term capability; the number describes long-term performance. Nothing
crashes, no test fails, and a capability report goes to a customer overstating
or understating the process. This is the most common serious defect in SPC
software and it is designed out here rather than reviewed for.

### 1.2 Units are explicit and typed at boundaries. **[ENFORCED]**

A `Measurement` carries its unit. Bare floats do not cross module boundaries
where a unit is meaningful.

```python
# WRONG
def evaluate(thickness: float) -> bool: ...

# RIGHT
def evaluate(thickness: Measurement) -> Violation | None: ...
```

**Failure prevented:** ångström/nanometre and °C/K confusion. A factor-of-ten
error in a film thickness looks entirely plausible on a chart.

### 1.3 Cite the source of every formula.

Every statistical function names its reference in the docstring, precisely
enough for a reviewer to check the implementation without trusting the author.

```python
def d2_constant(subgroup_size: int) -> float:
    """Return the d2 unbiasing constant for range-based sigma estimation.

    sigma_hat = R_bar / d2(n)

    References
    ----------
    Montgomery, D.C. (2019). *Introduction to Statistical Quality Control*,
    8th ed., Appendix Table VI.
    NIST/SEMATECH e-Handbook of Statistical Methods, §6.3.2.
    """
```

**Failure prevented:** a transcribed constant that is subtly wrong. `d2` for
n=2 is 1.128, and 1.182 looks equally reasonable to a reviewer with no
reference to check against.

Citations for numerical values come from NIST/SEMATECH or Montgomery only —
both publicly obtainable, so a reviewer can actually check them. AIAG and SEMI
publications are cited for terminology and methodology, never for a number
([ADR-0017](DECISION_LOG.md#adr-0017)).

### 1.4 Never invent a value in a quality-critical path.

No silent defaults, no fallback constants, no interpolation to fill a gap, no
`except: pass`.

```python
# WRONG — a fabricated limit is indistinguishable from a real one downstream
limits = baseline.limits if baseline else DEFAULT_LIMITS

# RIGHT
if baseline is None:
    raise NoActiveBaselineError(parameter_id=parameter.id)
```

**Failure prevented:** a chart drawn with plausible-looking limits that
correspond to no real process. A missing input must produce a visible absence,
never a confident substitute.

### 1.5 Specification limits and control limits are never interchangeable. **[ENFORCED]**

Distinct types, no conversion, no shared base class offering a `.limits`
accessor. `import-linter` and the type checker enforce it.

**Failure prevented:** the defining error of bad SPC tooling — drawing spec
limits as control limits, which makes a chart incapable of detecting a shift
until material is already non-conforming.

---

## 2. Style and formatting **[ENFORCED]**

Ruff decides. Formatting is not discussed in review, because time spent on it
is time not spent on whether the statistics are right.

| Setting | Value |
|---|---|
| Line length | 100 |
| Quotes | Double |
| Import sorting | Ruff isort rules, `spc_platform` as first-party |
| Docstring convention | NumPy |
| Target version | py313 ([ADR-0016](DECISION_LOG.md#adr-0016)) |

Enabled rule sets: `E`, `W`, `F`, `I`, `N`, `D`, `UP`, `ANN`, `S`, `B`, `A`,
`C4`, `DTZ`, `T20`, `PT`, `RET`, `SIM`, `ARG`, `PTH`, `ERA`, `PL`, `NPY`,
`RUF`. Notable inclusions: `DTZ` (naive datetimes banned — every timestamp in a
fab context is meaningless without a timezone), `T20` (no stray `print`),
`ERA` (no commented-out code), `S` (bandit security patterns).

## 3. Typing **[ENFORCED]**

`mypy --strict`, with no exceptions granted in the domain or analytics layers.

```python
# Explicit array typing for numerical code
import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]

def moving_range(values: FloatArray) -> FloatArray: ...
```

- No implicit `Any`. Untyped third-party libraries get a stub or an explicitly
  justified, narrowly scoped `# type: ignore[code]` with a comment.
- Prefer `Sequence`/`Iterable` in parameters, concrete types in returns.
- Domain identifiers are `NewType`, not `str`: `LotId = NewType("LotId", str)`.
  A lot ID and a wafer ID must not be silently swappable.
- Model states with enums or literal unions, never bare strings.

## 4. Function and module design

**Pure by default in `analytics/`.** Data in, results out. No logging of
business events, no I/O, no clocks, no global state. This is what makes the
statistical test tier possible.

**No module-level side effects. [ENFORCED]** Importing `spc_platform` must not
open a connection, read a file, or configure logging. Import-time work makes
tests order-dependent and failures inexplicable.

**Small functions with a single reason to change.** A function that computes
limits, evaluates rules, and persists violations cannot be tested for any of
the three.

**Vectorise numerical work.** Per-point Python loops over measurement series
fail the performance budget by roughly two orders of magnitude at production
volume. Rule evaluation over zoned data is expressible as array operations.

**Return values, do not mutate arguments.** In particular, never modify an
input array in place; a caller holding the original data will observe silent
corruption.

## 5. Error handling

**A typed exception hierarchy**, rooted at `SPCPlatformError`, with specific
subclasses (`SchemaValidationError`, `NoActiveBaselineError`,
`InsufficientDataError`, `UnstableProcessError`). Callers catch what they can
handle.

**Exceptions carry context.** `InsufficientDataError(parameter_id=..., n=12,
required=25)` is actionable; `ValueError("not enough data")` sends someone into
the source.

**Fail fast and loudly at boundaries.** Schema violations quarantine the batch
and fail the run. A pipeline that skips bad rows and continues produces a chart
that is quietly wrong, which is worse than a pipeline that stops.

**Never swallow an exception.** No bare `except`, no `except: pass`. If a
failure is genuinely tolerable, catch the specific type, log it with context,
and record the degradation in the output.

**Statistical preconditions are checked, not assumed.** A function that
requires n ≥ 2, a positive sigma, or a non-degenerate series validates that and
raises. Silent division by a zero range produces `inf` limits, and an `inf`
plots as an empty chart that looks like a display bug rather than a data
problem.

## 6. Naming

Domain vocabulary comes from [GLOSSARY.md](GLOSSARY.md), exactly. If code and
glossary disagree, one of them is a defect.

| Concept | Name | Never |
|---|---|---|
| Lot identifier | `lot_id` | `batch_id`, `lotNo` |
| Wafer slot | `slot` | `position`, `index` |
| Measurement site | `site_id` | `point`, `location` |
| Upper control limit | `ucl` | `upper_limit` (ambiguous with spec) |
| Upper specification limit | `usl` | `upper_limit`, `max` |
| Short-term sigma | `sigma_within` | `sigma`, `std` |
| Long-term sigma | `sigma_overall` | `sigma`, `std` |
| Subgroup size | `subgroup_size` | `n` (except locally in a formula) |

Standard abbreviations from the SPC literature (`ucl`, `lcl`, `usl`, `lsl`,
`cp`, `cpk`, `ewma`, `msa`) are used as-is: expanding them makes the code
*less* readable to the domain expert who must review it.

## 7. Documentation in code

NumPy-style docstrings on every public function. For statistical functions,
four sections are mandatory: **Parameters** (with units and constraints),
**Returns**, **Raises**, and **References**.

```python
def control_limits_imr(
    values: FloatArray,
    sigma_multiplier: float = 3.0,
) -> IndividualsLimits:
    """Compute individuals-chart control limits from the average moving range.

    Sigma is estimated as MR_bar / d2(2), where d2(2) = 1.128. This is the
    short-term estimate and deliberately excludes between-point drift, so
    that drift remains detectable rather than being absorbed into the limits.

    Parameters
    ----------
    values
        Time-ordered individual measurements in the parameter's declared unit.
        At least 2 points; at least 25 recommended for a qualified baseline.
    sigma_multiplier
        Control limit width in sigma units. Default 3.0 (ARL_0 ~ 370).

    Returns
    -------
    IndividualsLimits
        Centre line and control limits, tagged with the estimator used.

    Raises
    ------
    InsufficientDataError
        If fewer than 2 values are supplied.
    DegenerateSeriesError
        If all moving ranges are zero, making limits undefined.

    References
    ----------
    Montgomery, D.C. (2019), 8th ed., §6.4.
    NIST/SEMATECH e-Handbook, §6.3.2.
    """
```

**Comments explain why, never what. [ENFORCED via `ERA`]** A comment restating
the code is noise; a comment recording a non-obvious constraint is essential.

```python
# WRONG
# Loop over the wafers
for wafer in lot.wafers: ...

# RIGHT
# Sites are NOT used as a rational subgroup: the within-wafer radial signature
# is systematic, and pooling it into sigma_within inflates the limits until the
# chart stops signalling. Wafer means are charted; the signature is handled in
# analytics/spatial/.
subgroups = [wafer.mean() for wafer in lot.wafers]
```

## 8. Configuration and constants

- **No magic numbers in code.** A statistical constant lives in
  `analytics/estimators/` with its citation; a process value lives in
  `configs/`. A `1.33` appearing inline in a comparison is a defect.
- **Configuration is parsed once at the boundary** into immutable Pydantic
  models. No function reads YAML or an environment variable.
- **Unknown configuration keys are errors.** A silently ignored typo in a rule
  set means the intended rule never runs, and nothing reports it.

## 9. Logging and audit

Two separate mechanisms with different obligations — see
[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) §3.6.

```python
log.info("chart_evaluated", parameter_id=p.id, n_points=len(v), n_violations=len(x))
```

- **Structured logging only.** Key-value fields, never interpolated prose.
- **Correlation ID on every entry**, so a request traces across pipeline,
  application, and API.
- **No measured values, credentials, or customer device names in operational
  logs.** Log the parameter identifier, not the value, unless the value is the
  point of the record. Redaction happens at the logging boundary.
- **Audit events are explicit calls**, not a side effect of logging. Every
  consequential action — limit change, baseline recalculation, disposition —
  records actor, timestamp, before/after, and reason.
- **Never log inside `analytics/`.** Purity is the point.

## 10. Testing obligations

Full detail in [TESTING_STRATEGY.md](TESTING_STRATEGY.md). The obligations that
bind at code-writing time:

- Any change to `analytics/` requires a case in `tests/statistical/` with an
  expected value from a **cited external source** — never a snapshot of what
  the function currently returns, which merely freezes a possible bug.
- Every fixed defect gets a regression test that fails against the old code.
- Every port gets a contract test that both the real and the fake adapter pass.
- Tests are named for the behaviour asserted, not the function called:
  `test_ewma_detects_one_sigma_shift_faster_than_shewhart`.

## 11. Git and review

- **Conventional Commits. [ENFORCED]** `feat:`, `fix:`, `refactor:`, `test:`,
  `docs:`, `chore:`, `perf:`. A `stat:` scope marks any change to statistical
  behaviour, so those commits are trivially findable in history.
- **Branches:** `feature/`, `fix/`, `docs/`, `refactor/`.
- **Small pull requests.** A 2 000-line PR is not reviewed; it is approved.
- **Documentation and `.cursor/rules/` update in the same PR** as the change
  they describe. Documentation deferred is documentation abandoned.
- **A change to statistical behaviour must state, in the PR, whether existing
  baselines, reports, or historical comparisons are invalidated.** Changing an
  estimator silently rewrites the meaning of every past number.

## 12. Rules for AI-generated code

The agent is a contributor and is held to the same standards, plus three that
address its characteristic failure modes:

1. **No plausible invention.** If a constant, threshold, or formula cannot be
   cited, it is not written. Statistical constants are the highest-risk
   category: they look authoritative and are unverifiable by inspection.
2. **No unrequested scope.** Additional "helpful" fallbacks, defaults, and
   `try`/`except` wrappers are exactly the silent-failure patterns §1.4 bans.
3. **Follow the layering, or stop and say so.** If a task appears to require an
   import that violates §1 of [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md),
   the design needs discussion — the rule does not get bent.

---

**Related:** [TESTING_STRATEGY.md](TESTING_STRATEGY.md) ·
[SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) ·
[GLOSSARY.md](GLOSSARY.md) ·
[TECH_STACK.md](TECH_STACK.md)
