"""Statistical self-checks that the data matches what the configuration asked for.

This is an independent implementation on purpose. It uses NumPy directly and
imports nothing from ``analytics/`` — a constraint enforced by ``import-linter``
rather than left to discipline.

The reason is not tidiness. A generator that verified its own output with the
estimators under test would produce a self-confirming benchmark: the same sign
error in both would cancel, the check would pass, and the platform's central
claim about its own correctness would rest on nothing. Two independent
implementations agreeing is evidence; one implementation agreeing with itself is
not.

Every estimator below is bias-corrected explicitly, because the corrections are
the part a reviewer needs to check. Subtracting a site profile estimated from
the same wafers removes degrees of freedom, and a check that ignored that would
report a within-wafer sigma that is systematically too small and call the
generator wrong.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import NamedTuple

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from spc_platform.simulation.manifests import DatasetManifest, FaultRecord, scale_key
from spc_platform.simulation.models import FaultKind, ValueDistribution

_MIN_WAFERS = 40
"""Below this, the sampling error swamps the quantity being checked."""

_MIN_SITES_FOR_SPATIAL = 5
_MIN_TOOLS = 2
_LEVEL_SIGMA_MULTIPLIER = 4.0
_RELATIVE_TOLERANCE = 0.20
_SYSTEMATIC_CORRELATION_FLOOR = 0.85


_LEVEL_DISTURBING_FAULTS = frozenset(
    {
        FaultKind.GRADUAL_DRIFT,
        FaultKind.STEP_SHIFT,
        FaultKind.CYCLIC,
        FaultKind.TOOL_EXCURSION,
        FaultKind.METROLOGY_DRIFT,
        FaultKind.OUTLIER,
    }
)
_SPREAD_DISTURBING_FAULTS = frozenset(
    {
        FaultKind.VARIANCE_INCREASE,
        FaultKind.SPATIAL_CHANGE,
        FaultKind.OUTLIER,
        FaultKind.GRADUAL_DRIFT,
        FaultKind.CYCLIC,
    }
)


@dataclass(frozen=True, slots=True)
class Check:
    """One comparison between a configured quantity and its realised value."""

    name: str
    subject: str
    configured: float
    observed: float
    tolerance: float
    passed: bool

    def describe(self) -> str:
        """Return a single readable line for an operator."""
        mark = "ok  " if self.passed else "FAIL"
        return (
            f"{mark} {self.subject:<34} {self.name:<20} "
            f"configured={self.configured:> 12.5g} observed={self.observed:> 12.5g} "
            f"tolerance=±{self.tolerance:.5g}"
        )


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """The outcome of validating one dataset against its manifest."""

    dataset_id: str
    checks: tuple[Check, ...]
    unchecked_subjects: tuple[str, ...] = ()
    """Characteristics nothing could be asserted about.

    Reported rather than dropped. A characteristic carrying a fault has no
    clean quantity to compare, and one with too few wafers cannot support an
    estimate — but a report that passed silently in either case would claim
    coverage it does not have.
    """

    @property
    def passed(self) -> bool:
        """Whether every check performed passed."""
        return all(check.passed for check in self.checks)

    @property
    def failures(self) -> tuple[Check, ...]:
        """The checks that failed."""
        return tuple(check for check in self.checks if not check.passed)

    def summary(self) -> str:
        """Return a full report, one line per check."""
        lines = [check.describe() for check in self.checks]
        verdict = "PASSED" if self.passed else f"FAILED ({len(self.failures)} checks)"
        lines.append(f"\n{self.dataset_id}: {len(self.checks)} checks, {verdict}")
        if self.unchecked_subjects:
            lines.append(
                f"{len(self.unchecked_subjects)} characteristics were not checked: "
                + ", ".join(self.unchecked_subjects)
            )
        return "\n".join(lines)


def _wafer_site_matrix(subset: pd.DataFrame) -> NDArray[np.float64]:
    """Return a dense (wafers x sites) matrix, dropping wafers with a gap.

    A wafer missing a site cannot contribute to a within-wafer decomposition,
    and filling the gap would invent the very structure being measured.
    """
    pivot = subset.pivot_table(
        index="wafer_id",
        columns="site_id",
        values="value",
        aggfunc="mean",
    )
    matrix = pivot.to_numpy(dtype=np.float64)
    complete = ~np.isnan(matrix).any(axis=1)
    return matrix[complete]


def _site_profile(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    """Estimate the systematic per-site offset from wafer-centred deviations."""
    deviations = matrix - matrix.mean(axis=1, keepdims=True)
    return np.asarray(deviations.mean(axis=0), dtype=np.float64)


def _within_wafer_sigma(matrix: NDArray[np.float64]) -> float:
    """Estimate the random within-wafer sigma, corrected for lost freedom.

    Both the wafer mean and the site profile are estimated from the same data,
    so the residual variance is deflated by ``(1 - 1/S)(1 - 1/W)``. Correcting
    for it is what makes the estimate comparable to the configured value.
    """
    wafers, sites = matrix.shape
    deviations = matrix - matrix.mean(axis=1, keepdims=True)
    residual = deviations - deviations.mean(axis=0, keepdims=True)
    deflation = (1.0 - 1.0 / sites) * (1.0 - 1.0 / wafers)
    return float(np.std(residual) / np.sqrt(deflation))


def _spatial_amplitude(matrix: NDArray[np.float64], within_sigma: float) -> float:
    """Estimate the systematic signature amplitude, less its sampling noise."""
    wafers, sites = matrix.shape
    profile = _site_profile(matrix)
    noise_variance = within_sigma**2 * (1.0 - 1.0 / sites) / wafers
    return float(np.sqrt(max(float(np.var(profile)) - noise_variance, 0.0)))


def _profile_reproducibility(matrix: NDArray[np.float64]) -> float:
    """Correlate the site profile of one half of the wafers against the other.

    This is the test that separates a systematic signature from noise. A real
    signature is the same shape on every wafer, so the two halves agree; noise
    correlates at zero. It is the exit criterion the roadmap states for this
    phase, expressed as a number rather than as an impression of a plot.
    """
    half = matrix.shape[0] // 2
    first = _site_profile(matrix[:half])
    second = _site_profile(matrix[half:])
    if np.std(first) == 0.0 or np.std(second) == 0.0:
        return 0.0
    return float(np.corrcoef(first, second)[0, 1])


def _tool_offset_checks(
    subset: pd.DataFrame,
    *,
    subject: str,
    configured: Mapping[str, float],
    sigma_lot: float,
    sigma_tool_offset: float,
) -> list[Check]:
    """Compare each tool's realised bias against the one the manifest records.

    Checking the offsets individually rather than checking their spread. The
    spread of two or three fixed numbers is estimated from two or three
    observations however long the dataset runs, so a spread check is noisy at
    every dataset size and cannot be made trustworthy by generating more data.
    Each tool's own mean, by contrast, is an average over all the lots that ran
    on it and tightens as the dataset grows.

    The comparison is between deviations from the grand mean, because the fleet
    is centred by construction and only the mismatch between its members is
    claimed.
    """
    lot_means = subset.groupby(["tool_id", "lot_id"], sort=True)["value"].mean()
    by_tool = lot_means.groupby("tool_id", sort=True)
    observed = {str(tool): float(value) for tool, value in by_tool.mean().items()}
    lots_per_tool = {str(tool): int(value) for tool, value in by_tool.count().items()}
    if len(observed) < _MIN_TOOLS:
        return []

    grand_mean = float(np.mean(list(observed.values())))
    expected_centre = float(np.mean([configured.get(tool, 0.0) for tool in observed]))

    checks: list[Check] = []
    for tool, mean in observed.items():
        expected = configured.get(tool)
        if expected is None:
            continue
        # Standard error of this tool's mean, from the lots it ran. The other
        # tools' noise enters through the grand mean, which is why the term is
        # doubled rather than taken alone.
        standard_error = sigma_lot * np.sqrt(2.0 / lots_per_tool[tool])
        tolerance = float(_LEVEL_SIGMA_MULTIPLIER * standard_error)
        if tolerance > sigma_tool_offset:
            # The tool ran too few lots to resolve a bias of the size claimed.
            # A check whose tolerance exceeds the quantity it is checking passes
            # whatever the data says, and counting it as coverage would overstate
            # what the dataset has been shown to contain.
            continue
        deviation = float(mean) - grand_mean
        target = expected - expected_centre
        checks.append(
            Check(
                name="tool_offset",
                subject=f"{subject} {tool}",
                configured=target,
                observed=deviation,
                tolerance=tolerance,
                passed=abs(deviation - target) <= tolerance,
            )
        )
    return checks


def _relative_check(
    name: str,
    subject: str,
    *,
    configured: float,
    observed: float,
    tolerance: float = _RELATIVE_TOLERANCE,
) -> Check:
    allowed = abs(configured) * tolerance
    return Check(
        name=name,
        subject=subject,
        configured=configured,
        observed=observed,
        tolerance=allowed,
        passed=abs(observed - configured) <= allowed,
    )


def subject_of(parameter_id: str, product_id: str) -> str:
    """Return the name a characteristic is reported under."""
    return f"{parameter_id}/{product_id}"


def _subjects_reached(fault: FaultRecord, frame: pd.DataFrame) -> set[str]:
    """Return the characteristics one fault actually touches.

    A fault leaves unset every field it does not scope itself to, and an unset
    field matches anything — so the reach has to be resolved against the data
    rather than read off the record. A gauge drift naming only
    ``MET-PROF-02`` reaches the parameters that profilometer measured and no
    others; treating it as reaching everything would suppress the level check
    across the whole dataset and leave the generator's central claim untested.
    """
    mask = pd.Series(data=True, index=frame.index)
    for column, value in (
        ("parameter_id", fault.parameter_id),
        ("product_id", fault.product_id),
        ("tool_id", fault.tool_id),
        ("chamber_id", fault.chamber_id),
        ("metrology_tool_id", fault.metrology_tool_id),
    ):
        if value is not None:
            mask &= frame[column] == str(value)

    reached = frame.loc[mask, ["parameter_id", "product_id"]].drop_duplicates()
    return {
        subject_of(str(parameter), str(product))
        for parameter, product in reached.itertuples(index=False)
    }


@dataclass(frozen=True, slots=True)
class _Disturbed:
    """Which characteristics carry a fault, and cannot be checked as clean.

    Scoped per characteristic rather than per parameter: a drift injected on
    DEV-A leaves the same parameter on DEV-B clean, and discarding that
    distinction would throw away most of the dataset's verifiable surface.
    """

    level: frozenset[str]
    spread: frozenset[str]

    @classmethod
    def from_manifest(cls, manifest: DatasetManifest, frame: pd.DataFrame) -> _Disturbed:
        level: set[str] = set()
        spread: set[str] = set()
        for fault in manifest.faults:
            subjects = _subjects_reached(fault, frame)
            if fault.kind in _LEVEL_DISTURBING_FAULTS:
                level |= subjects
            if fault.kind in _SPREAD_DISTURBING_FAULTS:
                spread |= subjects
        return cls(level=frozenset(level), spread=frozenset(spread))


def validate_dataset(frame: pd.DataFrame, manifest: DatasetManifest) -> ValidationReport:
    """Check a generated dataset against the components it was configured with.

    Only clean characteristics are checked. A parameter carrying an injected
    drift is *supposed* to sit off target, and asserting otherwise would fail
    the generator for doing its job.

    Parameters
    ----------
    frame
        The measurement table, as written.
    manifest
        The manifest describing it.

    Returns
    -------
    ValidationReport
        One check per recoverable component per characteristic.
    """
    valid = frame[frame["measurement_status"] == "valid"]
    disturbed = _Disturbed.from_manifest(manifest, valid)
    checks: list[Check] = []
    unchecked: list[str] = []

    for parameter_physics in manifest.config.parameters:
        parameter_id = str(parameter_physics.parameter_id)
        is_poisson = parameter_physics.distribution is ValueDistribution.POISSON

        for entry in manifest.config.product_mix:
            product_id = str(entry.product_id)
            scales = manifest.component_scales.get(
                scale_key(parameter_physics.parameter_id, entry.product_id)
            )
            if scales is None:
                continue

            subset = valid[
                (valid["parameter_id"] == parameter_id) & (valid["product_id"] == product_id)
            ]
            if subset.empty:
                continue

            subject = subject_of(parameter_id, product_id)
            found = _checks_for_characteristic(
                subset,
                scales=scales,
                tool_offsets=manifest.tool_offsets.get(
                    scale_key(parameter_physics.parameter_id, entry.product_id), {}
                ),
                subject=subject,
                clean=_Clean(
                    level=subject not in disturbed.level,
                    spread=subject not in disturbed.spread and not is_poisson,
                ),
            )
            checks.extend(found)
            if not found:
                unchecked.append(subject)

    return ValidationReport(
        dataset_id=manifest.dataset_id,
        checks=tuple(checks),
        unchecked_subjects=tuple(sorted(unchecked)),
    )


class _Clean(NamedTuple):
    """Which of a characteristic's properties are undisturbed by any fault.

    Carried as a pair because the two travel together everywhere: a variance
    fault leaves the level checkable and the spread not, and a step shift the
    reverse, so neither is meaningful without the other alongside it.
    """

    level: bool
    spread: bool


def _checks_for_characteristic(
    subset: pd.DataFrame,
    *,
    scales: dict[str, float],
    tool_offsets: Mapping[str, float],
    subject: str,
    clean: _Clean,
) -> list[Check]:
    """Run every applicable check for one parameter on one product."""
    checks: list[Check] = []
    lot_count = int(subset["lot_id"].nunique())

    if clean.level and lot_count >= _MIN_TOOLS:
        allowed = _LEVEL_SIGMA_MULTIPLIER * scales["sigma_total"] / np.sqrt(lot_count)
        observed = float(subset["value"].mean())
        checks.append(
            Check(
                name="level",
                subject=subject,
                configured=scales["target"],
                observed=observed,
                tolerance=float(allowed),
                passed=abs(observed - scales["target"]) <= allowed,
            )
        )

    # Gated on a clean level rather than on a clean spread: anything that moves
    # the mean over time leaks into the per-tool means, because tools do not run
    # equal shares of the lots before and after an onset.
    if clean.level and tool_offsets:
        checks.extend(
            _tool_offset_checks(
                subset,
                subject=subject,
                configured=tool_offsets,
                sigma_lot=scales["sigma_lot"],
                sigma_tool_offset=scales["sigma_tool_offset"],
            )
        )

    if not clean.spread:
        return checks

    matrix = _wafer_site_matrix(subset)
    wafers, sites = matrix.shape if matrix.size else (0, 0)

    if wafers >= _MIN_WAFERS and sites >= _MIN_SITES_FOR_SPATIAL:
        within = _within_wafer_sigma(matrix)
        configured_within = float(np.hypot(scales["sigma_site"], scales["sigma_gauge"]))
        checks.append(
            _relative_check(
                "within_wafer_sigma",
                subject,
                configured=configured_within,
                observed=within,
            )
        )

        if scales["spatial_amplitude"] > 0.0:
            checks.append(
                _relative_check(
                    "spatial_amplitude",
                    subject,
                    configured=scales["spatial_amplitude"],
                    observed=_spatial_amplitude(matrix, within),
                )
            )
            correlation = _profile_reproducibility(matrix)
            checks.append(
                Check(
                    name="spatial_systematic",
                    subject=subject,
                    configured=1.0,
                    observed=correlation,
                    tolerance=1.0 - _SYSTEMATIC_CORRELATION_FLOOR,
                    passed=correlation >= _SYSTEMATIC_CORRELATION_FLOOR,
                )
            )

    return checks
