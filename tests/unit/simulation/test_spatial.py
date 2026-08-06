"""Sampling plans and within-wafer signatures."""

from __future__ import annotations

import numpy as np
import pytest

from spc_platform.common.errors import SimulationConfigError
from spc_platform.domain.enums import SpatialSignature
from spc_platform.simulation.spatial import (
    SUPPORTED_SITE_COUNTS,
    USABLE_RADIUS_MM,
    sampling_plan,
    signature_profile,
)


@pytest.mark.parametrize("site_count", SUPPORTED_SITE_COUNTS)
def test_plan_has_the_requested_number_of_sites(site_count: int) -> None:
    assert sampling_plan(site_count).shape == (site_count, 2)


@pytest.mark.parametrize("site_count", SUPPORTED_SITE_COUNTS)
def test_every_site_lies_inside_the_usable_radius(site_count: int) -> None:
    """A site in the edge exclusion ring names a location with no measurable die."""
    plan = sampling_plan(site_count)
    radii = np.hypot(plan[:, 0], plan[:, 1])

    assert float(radii.max()) <= USABLE_RADIUS_MM


@pytest.mark.parametrize("site_count", SUPPORTED_SITE_COUNTS)
def test_site_one_is_always_the_wafer_centre(site_count: int) -> None:
    """A site_id has to mean the same location in every dataset."""
    np.testing.assert_array_equal(sampling_plan(site_count)[0], np.zeros(2))


@pytest.mark.parametrize("site_count", SUPPORTED_SITE_COUNTS)
def test_coordinates_carry_no_floating_point_debris(site_count: int) -> None:
    """A site nominally on an axis must read as 0, not as 4.6e-15."""
    plan = sampling_plan(site_count)

    np.testing.assert_array_equal(plan, np.round(plan, 6))


def test_plans_are_identical_across_calls() -> None:
    np.testing.assert_array_equal(sampling_plan(13), sampling_plan(13))


def test_an_undeclared_site_count_is_refused() -> None:
    """Interpolating a plan would put sites where no metrology recipe measures."""
    with pytest.raises(SimulationConfigError, match="no sampling plan"):
        sampling_plan(7)


@pytest.mark.parametrize(
    "kind",
    [SpatialSignature.RADIAL, SpatialSignature.EDGE, SpatialSignature.ASYMMETRIC],
)
def test_a_signature_does_not_move_the_wafer_mean(kind: SpatialSignature) -> None:
    """The property that makes a wafer-mean chart blind to a spatial signature."""
    profile = signature_profile(kind, sampling_plan(13), amplitude=2.5)

    assert float(profile.mean()) == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize(
    "kind",
    [SpatialSignature.RADIAL, SpatialSignature.EDGE, SpatialSignature.ASYMMETRIC],
)
def test_amplitude_is_the_across_site_standard_deviation(kind: SpatialSignature) -> None:
    """Amplitude must mean the same thing in nanometres and in ohms per square."""
    profile = signature_profile(kind, sampling_plan(13), amplitude=2.5)

    assert float(np.std(profile)) == pytest.approx(2.5, rel=1e-9)


def test_the_none_signature_imposes_nothing() -> None:
    profile = signature_profile(SpatialSignature.NONE, sampling_plan(13), amplitude=2.5)

    np.testing.assert_array_equal(profile, np.zeros(13))


def test_a_single_site_plan_has_no_shape_to_impose() -> None:
    """One site cannot express a within-wafer pattern, whatever the amplitude."""
    profile = signature_profile(SpatialSignature.RADIAL, sampling_plan(1), amplitude=9.0)

    np.testing.assert_array_equal(profile, np.zeros(1))


def test_the_radial_signature_rises_from_centre_to_edge() -> None:
    plan = sampling_plan(13)
    profile = signature_profile(SpatialSignature.RADIAL, plan, amplitude=1.0)
    radii = np.hypot(plan[:, 0], plan[:, 1])

    ordered = profile[np.argsort(radii)]
    assert np.all(np.diff(ordered) >= -1e-12)


def test_the_edge_signature_is_concentrated_at_the_outer_ring() -> None:
    """A radial fit will not represent this, which is why the two are distinct."""
    plan = sampling_plan(13)
    profile = signature_profile(SpatialSignature.EDGE, plan, amplitude=1.0)
    radii = np.hypot(plan[:, 0], plan[:, 1])
    outermost = radii >= radii.max() - 1e-9

    assert float(profile[outermost].min()) > float(profile[~outermost].max())


def test_the_asymmetric_signature_is_not_rotationally_symmetric() -> None:
    """Two sites at equal radius must differ, or a radial statistic would see it."""
    plan = sampling_plan(13)
    profile = signature_profile(SpatialSignature.ASYMMETRIC, plan, amplitude=1.0)
    left = profile[np.argmin(plan[:, 0])]
    right = profile[np.argmax(plan[:, 0])]

    assert float(right) > 0.0 > float(left)
