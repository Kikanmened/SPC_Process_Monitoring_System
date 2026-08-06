"""Capability indices against published worked examples and analytical invariants.

The arithmetic here is four divisions, so a test that only checks the arithmetic
tests nothing. What is worth testing is the part that goes wrong in practice:
that the two sigmas do not get swapped, that a single-sided specification does
not silently acquire a Cp, that an unstable process is refused, and that Cpm
falls below Cpk exactly when the process is off target rather than off centre.

References
----------
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., Example 8.1 (piston ring inner diameter), §8.2-8.3.
NIST/SEMATECH e-Handbook of Statistical Methods, §6.1.6.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spc_platform.analytics.capability import (
    CapabilityContext,
    CapabilityResult,
    DispersionPair,
    SpecificationSide,
    StabilityStatus,
    capability,
)
from spc_platform.analytics.estimators.sigma import SigmaEstimate
from spc_platform.common.errors import (
    DegenerateSeriesError,
    InsufficientDataError,
    UnstableProcessError,
)
from spc_platform.common.types import FloatArray
from spc_platform.domain.enums import SigmaEstimator
from spc_platform.domain.ids import ParameterId, ProductId, StepId, UnitSymbol
from spc_platform.domain.specification_limit import SpecificationLimit

WINDOW = (
    datetime(2026, 1, 1, tzinfo=UTC),
    datetime(2026, 1, 31, tzinfo=UTC),
)

PISTON_RING_SIGMA = 0.0099
"""R-bar / d2 = 0.023 / 2.326 for the piston ring data (Montgomery Example 8.1).

Montgomery rounds to this before computing the indices, so reproducing his
published Cp of 1.68 means starting from the number he started from.
"""


def specification(
    *,
    lsl: float | None = 73.95,
    usl: float | None = 74.05,
    target: float | None = None,
) -> SpecificationLimit:
    """Build a specification for the piston ring characteristic."""
    return SpecificationLimit(
        parameter_id=ParameterId("inner_diameter"),
        product_id=ProductId("piston_ring"),
        step_id=StepId("grind"),
        unit=UnitSymbol("mm"),
        lsl=lsl,
        usl=usl,
        target=target,
        effective_from=WINDOW[0],
    )


def dispersion(
    within: float = PISTON_RING_SIGMA,
    overall: float | None = None,
) -> DispersionPair:
    """Pair a short-term and long-term sigma, defaulting the two to equal."""
    return DispersionPair(
        within=SigmaEstimate(
            value=within,
            estimator=SigmaEstimator.R_BAR_D2,
            subgroup_size=5,
            n_subgroups=25,
        ),
        overall=SigmaEstimate(
            value=overall if overall is not None else within,
            estimator=SigmaEstimator.SAMPLE_STD,
            subgroup_size=1,
            n_subgroups=125,
        ),
    )


def stable(**overrides: object) -> CapabilityContext:
    """Build a context for a process demonstrated to be in control."""
    fields: dict[str, object] = {
        "window": WINDOW,
        "stability": StabilityStatus.IN_CONTROL,
    }
    fields.update(overrides)
    return CapabilityContext(**fields)  # type: ignore[arg-type]


def centred_on(mean: float, sigma: float, n: int = 125) -> FloatArray:
    """Build a sample with exactly the requested mean.

    The indices depend on the sample only through its mean and, for Cpm, its
    distance from target; sigma arrives separately as an estimate. Constructing
    the mean exactly keeps the reference comparison free of sampling noise.
    """
    raw = np.linspace(-1.0, 1.0, n)
    return mean + sigma * (raw - raw.mean())


class TestTheMontgomeryPistonRings:
    """Example 8.1: 125 rings, 25 subgroups of 5, USL 74.05 and LSL 73.95.

    Montgomery reports Cp = 1.68 and Cpk = 1.65 from x-bar-bar = 74.001 and
    sigma-hat = R-bar / d2 = 0.0099.
    """

    @pytest.fixture
    def result(self) -> CapabilityResult:
        """Assess capability from the published summary statistics."""
        return capability(
            centred_on(74.001, PISTON_RING_SIGMA),
            specification(),
            dispersion=dispersion(),
            context=stable(),
        )

    def test_cp_matches_the_published_value(self, result: CapabilityResult) -> None:
        """Cp = 0.10 / (6 x 0.0099) = 1.68."""
        assert result.within.cp == pytest.approx(1.68, abs=0.005)

    def test_cpk_matches_the_published_value(self, result: CapabilityResult) -> None:
        """Cpk = min(1.65, 1.72) = 1.65, the process being above centre."""
        assert result.within.cpk == pytest.approx(1.65, abs=0.005)

    def test_the_upper_side_is_the_binding_one(self, result: CapabilityResult) -> None:
        """The mean sits above the midpoint, so the upper index is the smaller."""
        assert result.within.cpu is not None
        assert result.within.cpl is not None
        assert result.within.cpu < result.within.cpl
        assert result.within.cpk == result.within.cpu

    def test_both_specification_sides_are_recorded(self, result: CapabilityResult) -> None:
        """A two-sided specification is reported as such."""
        assert result.specification_side is SpecificationSide.BOTH


class TestTheTwoSigmasStayApart:
    """Cp and Pp are the same arithmetic over different estimates (FR-P03).

    Reporting one as the other is the most common way a capability claim is
    overstated, so the estimator has to survive on the result.
    """

    def test_each_family_carries_its_own_estimator(self) -> None:
        """The within indices name the short-term estimator and vice versa."""
        result = capability(
            centred_on(74.0, 0.01),
            specification(),
            dispersion=dispersion(within=0.0099, overall=0.0198),
            context=stable(),
        )
        assert result.within.estimator is SigmaEstimator.R_BAR_D2
        assert result.overall.estimator is SigmaEstimator.SAMPLE_STD

    def test_a_drifting_process_halves_its_long_term_indices(self) -> None:
        """Doubling the long-term sigma halves Pp against Cp, exactly."""
        result = capability(
            centred_on(74.0, 0.01),
            specification(),
            dispersion=dispersion(within=0.0099, overall=0.0198),
            context=stable(),
        )
        assert result.within.cp is not None
        assert result.overall.cp is not None
        assert result.overall.cp == pytest.approx(result.within.cp / 2.0)

    def test_the_sigma_ratio_names_where_the_gain_is(self) -> None:
        """A ratio of two says drift dominates the noise between units."""
        result = capability(
            centred_on(74.0, 0.01),
            specification(),
            dispersion=dispersion(within=0.0099, overall=0.0198),
            context=stable(),
        )
        assert result.sigma_ratio == pytest.approx(2.0)


class TestTheSingleSidedCase:
    """A specification with one limit has no width, so it has no Cp (FR-P08)."""

    def test_an_upper_only_specification_has_no_cp(self) -> None:
        """Returning half the two-sided formula would double the reported figure."""
        result = capability(
            centred_on(74.0, 0.01),
            specification(lsl=None),
            dispersion=dispersion(),
            context=stable(),
        )
        assert result.within.cp is None
        assert result.within.cpl is None
        assert result.specification_side is SpecificationSide.UPPER_ONLY

    def test_cpk_is_the_only_available_side(self) -> None:
        """With one limit, Cpk is that side's index rather than a minimum of two."""
        result = capability(
            centred_on(74.0, 0.01),
            specification(usl=None),
            dispersion=dispersion(),
            context=stable(),
        )
        assert result.within.cpk == result.within.cpl
        assert result.specification_side is SpecificationSide.LOWER_ONLY


class TestTaguchiCapability:
    """Cpm penalises distance from target, which Cpk does not (FR-P02)."""

    def test_cpm_is_absent_without_a_target(self) -> None:
        """There is nothing to be off, so the index does not exist."""
        result = capability(
            centred_on(74.0, 0.01),
            specification(),
            dispersion=dispersion(),
            context=stable(),
        )
        assert result.cpm is None

    def test_cpm_equals_pp_when_the_process_sits_on_target(self) -> None:
        """With no offset the penalty term vanishes and the two coincide."""
        result = capability(
            centred_on(74.0, 0.01),
            specification(target=74.0),
            dispersion=dispersion(),
            context=stable(),
        )
        assert result.cpm == pytest.approx(result.overall.cp)

    def test_cpm_falls_below_pp_once_the_process_leaves_target(self) -> None:
        """The offset enters the denominator, so any departure costs capability."""
        result = capability(
            centred_on(74.02, 0.01),
            specification(target=74.0),
            dispersion=dispersion(),
            context=stable(),
        )
        assert result.overall.cp is not None
        assert result.cpm is not None
        assert result.cpm < result.overall.cp

    def test_cpm_distinguishes_centred_from_on_target(self) -> None:
        """Cpk cannot tell these apart when the target is not the midpoint.

        Both processes sit at the midpoint of the specification, so both have
        the same Cpk. Only the one whose target is elsewhere is penalised.
        """
        at_midpoint = capability(
            centred_on(74.0, 0.01),
            specification(target=74.0),
            dispersion=dispersion(),
            context=stable(),
        )
        off_target = capability(
            centred_on(74.0, 0.01),
            specification(target=73.99),
            dispersion=dispersion(),
            context=stable(),
        )
        assert at_midpoint.within.cpk == pytest.approx(off_target.within.cpk)
        assert at_midpoint.cpm is not None
        assert off_target.cpm is not None
        assert off_target.cpm < at_midpoint.cpm


class TestTheRefusals:
    """What the module will not compute, and why."""

    def test_an_unstable_process_is_refused(self) -> None:
        """A Cpk from an out-of-control process describes no distribution (FR-P04)."""
        with pytest.raises(UnstableProcessError):
            capability(
                centred_on(74.0, 0.01),
                specification(),
                dispersion=dispersion(),
                context=stable(stability=StabilityStatus.OUT_OF_CONTROL),
            )

    def test_an_unassessed_process_is_refused(self) -> None:
        """Not having looked is not the same as having looked and found nothing."""
        with pytest.raises(UnstableProcessError):
            capability(
                centred_on(74.0, 0.01),
                specification(),
                dispersion=dispersion(),
                context=stable(stability=StabilityStatus.NOT_ASSESSED),
            )

    def test_the_refusal_can_be_waived_deliberately(self) -> None:
        """Turning it off is possible, and leaves the finding on the result."""
        result = capability(
            centred_on(74.0, 0.01),
            specification(),
            dispersion=dispersion(),
            context=stable(
                stability=StabilityStatus.OUT_OF_CONTROL,
                require_stable=False,
            ),
        )
        assert result.stability is StabilityStatus.OUT_OF_CONTROL

    def test_a_single_observation_is_refused(self) -> None:
        """One point has no capability to describe."""
        with pytest.raises(InsufficientDataError):
            capability(
                np.array([74.0]),
                specification(),
                dispersion=dispersion(),
                context=stable(),
            )

    def test_a_zero_sigma_is_refused(self) -> None:
        """Every index would be infinite, which reports as spectacular capability."""
        with pytest.raises(DegenerateSeriesError):
            capability(
                centred_on(74.0, 0.01),
                specification(),
                dispersion=dispersion(within=0.0),
                context=stable(),
            )


class TestTheInvariants:
    """Properties that hold for every process, checked by construction."""

    @settings(max_examples=200, deadline=None)
    @given(
        mean=st.floats(min_value=73.96, max_value=74.04),
        sigma=st.floats(min_value=1e-3, max_value=2e-2),
    )
    def test_cpk_never_exceeds_cp(self, mean: float, sigma: float) -> None:
        """Actual capability cannot beat potential capability.

        Cp measures the width alone; Cpk measures the width and the position.
        Position can only cost, never pay, so Cpk <= Cp for every process.
        """
        result = capability(
            centred_on(mean, sigma),
            specification(),
            dispersion=dispersion(within=sigma),
            context=stable(),
        )
        assert result.within.cp is not None
        assert result.within.cpk <= result.within.cp + 1e-12

    @settings(max_examples=200, deadline=None)
    @given(
        mean=st.floats(min_value=73.96, max_value=74.04),
        sigma=st.floats(min_value=1e-3, max_value=2e-2),
        scale=st.floats(min_value=0.5, max_value=4.0),
    )
    def test_the_indices_are_free_of_units(self, mean: float, sigma: float, scale: float) -> None:
        """Rescaling the data and the specification together changes nothing.

        A capability index is a ratio of two lengths, so working in microns
        rather than millimetres must not move it. If it did, the number would
        depend on how the fab happened to record the measurement.
        """
        plain = capability(
            centred_on(mean, sigma),
            specification(),
            dispersion=dispersion(within=sigma),
            context=stable(),
        )
        rescaled = capability(
            centred_on(mean * scale, sigma * scale),
            specification(lsl=73.95 * scale, usl=74.05 * scale),
            dispersion=dispersion(within=sigma * scale),
            context=stable(),
        )
        assert rescaled.within.cpk == pytest.approx(plain.within.cpk, rel=1e-9)
