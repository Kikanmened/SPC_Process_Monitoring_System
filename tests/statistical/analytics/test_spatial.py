"""Spatial signature classification recovers known wafer patterns (FR-S02).

The signatures are imposed by the synthetic generator's profile functions; the
classifier under test does not share those functions (ADR-0021). Recovery here
is therefore evidence that the geometric statistics find the physical shape,
not that two copies of the same formula agree.
"""

from __future__ import annotations

import numpy as np
import pytest

from spc_platform.analytics.spatial import (
    MIN_SITES_FOR_SIGNATURE,
    WaferField,
    classify_spatial_signature,
)
from spc_platform.common.errors import InsufficientSitesError
from spc_platform.domain.enums import SpatialSignature
from spc_platform.simulation.spatial import sampling_plan, signature_profile

pytestmark = pytest.mark.statistical

AMPLITUDE = 2.0
"""Signature standard deviation across sites, in arbitrary units."""

SITE_NOISE = 0.3
"""Per-site noise used in the noisy recovery cases."""

FALSE_POSITIVE_BUDGET = 0.05
"""Maximum fraction of unstructured wafers allowed to receive a non-none label.

Stated with the classifier: on a thirteen-site plan under unit noise the
measured rate sits well below this.
"""


@pytest.fixture(scope="module")
def plan_13() -> np.ndarray:
    """Thirteen-site sampling plan coordinates."""
    return sampling_plan(13)


class TestRecoveryFromKnownSignatures:
    """Each configured signature is recovered when it is the only shape present."""

    @pytest.mark.parametrize(
        "kind",
        [
            SpatialSignature.RADIAL,
            SpatialSignature.EDGE,
            SpatialSignature.ASYMMETRIC,
        ],
    )
    def test_a_clean_signature_is_recovered(
        self, plan_13: np.ndarray, kind: SpatialSignature
    ) -> None:
        """No noise: the geometric predictor matching the shape wins clearly."""
        values = signature_profile(kind, plan_13, AMPLITUDE)
        result = classify_spatial_signature(WaferField(plan_13, values))
        assert result.signature is kind
        assert result.statistic >= result.threshold
        assert result.sites_used == 13

    @pytest.mark.parametrize(
        "kind",
        [
            SpatialSignature.RADIAL,
            SpatialSignature.EDGE,
            SpatialSignature.ASYMMETRIC,
        ],
    )
    def test_a_noisy_signature_is_still_recovered(
        self, plan_13: np.ndarray, kind: SpatialSignature
    ) -> None:
        """Site noise at 15% of amplitude does not flip the label.

        Seeded so the case is reproducible; fifty wafers give the recovery
        rate a chance to fail if the classifier is only right on one draw.
        """
        rng = np.random.default_rng(20260805 + hash(kind.value) % 10_000)
        recovered = 0
        for _ in range(50):
            values = signature_profile(kind, plan_13, AMPLITUDE) + rng.normal(
                0.0, SITE_NOISE, size=plan_13.shape[0]
            )
            if classify_spatial_signature(WaferField(plan_13, values)).signature is kind:
                recovered += 1
        assert recovered >= 45, f"{kind.value} recovered on only {recovered}/50 wafers"


class TestNoneIsTheDefault:
    """Unstructured wafers must not be forced into a named pattern (R-43)."""

    def test_a_flat_wafer_is_none(self, plan_13: np.ndarray) -> None:
        """Constant values have no shape; every score is zero."""
        values = np.full(plan_13.shape[0], 42.0)
        result = classify_spatial_signature(WaferField(plan_13, values))
        assert result.signature is SpatialSignature.NONE

    def test_the_generator_none_signature_is_none(self, plan_13: np.ndarray) -> None:
        """The generator's NONE profile is the zero vector."""
        values = signature_profile(SpatialSignature.NONE, plan_13, AMPLITUDE)
        result = classify_spatial_signature(WaferField(plan_13, values))
        assert result.signature is SpatialSignature.NONE

    def test_unstructured_noise_stays_below_the_false_positive_budget(
        self, plan_13: np.ndarray
    ) -> None:
        """Unit-noise wafers are labelled none at the stated rate.

        This is the case that matters more than recovery: a classifier that
        must choose among three patterns will invent one in noise.
        """
        rng = np.random.default_rng(20260805)
        labelled = 0
        trials = 400
        for _ in range(trials):
            values = np.asarray(
                rng.normal(0.0, 1.0, size=int(plan_13.shape[0])),
                dtype=np.float64,
            )
            if (
                classify_spatial_signature(WaferField(plan_13, values)).signature
                is not SpatialSignature.NONE
            ):
                labelled += 1
        rate = labelled / trials
        assert rate <= FALSE_POSITIVE_BUDGET, (
            f"false-positive rate {rate:.3f} exceeds budget {FALSE_POSITIVE_BUDGET}"
        )


class TestRefusals:
    """Too few sites are a hard error, not a silent none."""

    def test_fewer_than_the_minimum_sites_is_refused(self) -> None:
        """A five-site plan confounds radial with edge and overfits noise."""
        coords = sampling_plan(5)
        values = np.zeros(5)
        with pytest.raises(InsufficientSitesError, match="too few sites"):
            WaferField(coords, values)

    def test_the_minimum_matches_the_smallest_separating_plan(self) -> None:
        """Nine is the smallest plan with two distinct radial rings."""
        assert MIN_SITES_FOR_SIGNATURE == 9
        field = WaferField(sampling_plan(9), np.zeros(9))
        assert field.n_sites == 9
