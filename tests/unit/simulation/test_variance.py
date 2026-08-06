"""Resolving a declared variance shape into absolute sigmas."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np
import pytest

from spc_platform.common.errors import SimulationConfigError
from spc_platform.domain.enums import SpatialSignature
from spc_platform.domain.ids import ParameterId, ProductId, StepId, UnitSymbol
from spc_platform.domain.specification_limit import SpecificationLimit
from spc_platform.simulation.models import (
    ParameterPhysics,
    RandomWeights,
    SystematicFractions,
    VarianceProfile,
)
from spc_platform.simulation.variance import fixed_offsets, resolve_scales, slot_profile

PROFILE = VarianceProfile(
    random_weights=RandomWeights(lot=0.5, wafer=0.5, site_residual=0.5, gauge=0.5),
    systematic=SystematicFractions(tool_offset=0.4, chamber_offset=0.3, slot=0.2, spatial=0.6),
)


def a_specification(
    *,
    lsl: float | None = 88.0,
    usl: float | None = 112.0,
    target: float | None = 100.0,
) -> SpecificationLimit:
    """Build a specification limit for a two-sided characteristic."""
    return SpecificationLimit(
        parameter_id=ParameterId("POLY_CD"),
        product_id=ProductId("DEV-A"),
        step_id=StepId("POLY_ETCH"),
        unit=UnitSymbol("nm"),
        lsl=lsl,
        usl=usl,
        target=target,
        effective_from=datetime(2024, 1, 1, tzinfo=UTC),
    )


def physics(**overrides: object) -> ParameterPhysics:
    """Build parameter physics, defaulting to a Cp-scaled two-sided parameter."""
    fields: dict[str, object] = {"parameter_id": ParameterId("POLY_CD"), "target_cp": 1.5}
    fields.update(overrides)
    return ParameterPhysics.model_validate(fields)


def test_target_cp_derives_sigma_from_the_specification_width() -> None:
    """Cp is defined over a six-sigma span (Montgomery §8.3): 24 / (6 x 1.5) = 2.667."""
    scales = resolve_scales(physics(target_cp=1.5), PROFILE, a_specification())

    assert scales.sigma_total == pytest.approx(24.0 / 9.0)


def test_random_components_combine_in_quadrature_to_the_total() -> None:
    scales = resolve_scales(physics(), PROFILE, a_specification())

    combined = np.hypot(
        np.hypot(scales.sigma_lot, scales.sigma_wafer),
        np.hypot(scales.sigma_site, scales.sigma_gauge),
    )
    assert float(combined) == pytest.approx(scales.sigma_total)


def test_systematic_terms_sit_outside_the_random_total() -> None:
    """Why Cp and Pp differ on real data, and must differ here."""
    scales = resolve_scales(physics(), PROFILE, a_specification())

    assert scales.sigma_tool_offset == pytest.approx(0.4 * scales.sigma_total)
    assert scales.sigma_chamber_offset == pytest.approx(0.3 * scales.sigma_total)
    assert scales.slot_amplitude == pytest.approx(0.2 * scales.sigma_total)


def test_sigma_total_is_taken_literally_when_declared() -> None:
    scales = resolve_scales(physics(target_cp=None, sigma_total=3.5), PROFILE, a_specification())

    assert scales.sigma_total == pytest.approx(3.5)


def test_a_parameter_without_a_signature_gets_no_spatial_amplitude() -> None:
    """A parameter with no signature records no spatial amplitude.

    Recording the profile's figure would put a number in the manifest that no
    measurement realises, and the manifest is the ground truth.
    """
    scales = resolve_scales(
        physics(spatial_signature=SpatialSignature.NONE),
        PROFILE,
        a_specification(),
    )

    assert scales.spatial_amplitude == 0.0


def test_a_parameter_with_a_signature_gets_the_profile_amplitude() -> None:
    scales = resolve_scales(
        physics(spatial_signature=SpatialSignature.RADIAL),
        PROFILE,
        a_specification(),
    )

    assert scales.spatial_amplitude == pytest.approx(0.6 * scales.sigma_total)


def test_the_midpoint_is_used_when_a_two_sided_spec_declares_no_target() -> None:
    scales = resolve_scales(physics(), PROFILE, a_specification(target=None))

    assert scales.target == pytest.approx(100.0)


def test_a_single_sided_spec_without_a_target_is_refused() -> None:
    """There is no level for the process to sit at, and inventing one hides it."""
    with pytest.raises(SimulationConfigError, match="no level to sit at"):
        resolve_scales(physics(), PROFILE, a_specification(lsl=None, target=None))


def test_target_cp_against_a_single_sided_spec_is_refused() -> None:
    """No width to divide; the configuration has to declare sigma_total instead."""
    with pytest.raises(SimulationConfigError, match="two-sided specification"):
        resolve_scales(physics(), PROFILE, a_specification(lsl=None))


class TestFixedOffsets:
    """Persistent tool and chamber biases."""

    def test_offsets_are_centred_and_scaled_exactly(self) -> None:
        """The offsets are centred on zero and scaled to the configured spread.

        Exactly, not approximately: these are specified, not sampled, and a
        variance decomposition of the data is checked against this figure.
        """
        offsets = fixed_offsets(("A", "B", "C", "D"), 1.5, master_seed=11, stream="tool")
        values = np.array(list(offsets.values()))

        assert float(values.mean()) == pytest.approx(0.0, abs=1e-12)
        assert float(np.std(values)) == pytest.approx(1.5, rel=1e-12)

    def test_offsets_are_reproducible(self) -> None:
        first = fixed_offsets(("A", "B", "C"), 1.0, master_seed=11, stream="tool")
        second = fixed_offsets(("A", "B", "C"), 1.0, master_seed=11, stream="tool")

        assert first == second

    def test_offsets_do_not_depend_on_the_order_the_fleet_is_listed(self) -> None:
        """A tool's bias is a property of the tool, not of the YAML it appears in."""
        forwards = fixed_offsets(("A", "B", "C"), 1.0, master_seed=11, stream="tool")
        backwards = fixed_offsets(("C", "B", "A"), 1.0, master_seed=11, stream="tool")

        assert forwards == backwards

    def test_tool_and_chamber_streams_differ(self) -> None:
        tools = fixed_offsets(("A", "B", "C"), 1.0, master_seed=11, stream="tool")
        chambers = fixed_offsets(("A", "B", "C"), 1.0, master_seed=11, stream="chamber")

        assert tools != chambers

    def test_a_single_member_fleet_has_no_mismatch(self) -> None:
        """One tool cannot mismatch itself, and a bias would move it off target."""
        assert fixed_offsets(("A",), 2.0, master_seed=11, stream="tool") == {"A": 0.0}

    def test_an_empty_fleet_yields_no_offsets(self) -> None:
        assert fixed_offsets((), 2.0, master_seed=11, stream="tool") == {}


class TestSlotProfile:
    """Position-in-carrier effect."""

    def test_the_profile_is_centred_and_scaled_over_the_whole_carrier(self) -> None:
        slots = np.arange(1, 26, dtype=np.int_)
        profile = slot_profile(slots, amplitude=0.8, wafers_per_lot=25)

        assert float(profile.mean()) == pytest.approx(0.0, abs=1e-12)
        assert float(np.std(profile)) == pytest.approx(0.8, rel=1e-12)

    def test_a_slot_keeps_its_offset_whichever_slots_are_sampled(self) -> None:
        """Otherwise a control plan's sampling choice would change the physics."""
        full = slot_profile(np.arange(1, 26, dtype=np.int_), 0.8, wafers_per_lot=25)
        sampled_slots = np.array([1, 13, 25], dtype=np.int_)
        sampled = slot_profile(sampled_slots, 0.8, wafers_per_lot=25)

        np.testing.assert_allclose(sampled, full[sampled_slots - 1])

    def test_zero_amplitude_imposes_nothing(self) -> None:
        profile = slot_profile(np.array([1, 2, 3], dtype=np.int_), 0.0, wafers_per_lot=25)

        np.testing.assert_array_equal(profile, np.zeros(3))

    def test_a_single_wafer_carrier_has_no_position_effect(self) -> None:
        profile = slot_profile(np.array([1], dtype=np.int_), 0.8, wafers_per_lot=1)

        np.testing.assert_array_equal(profile, np.zeros(1))
