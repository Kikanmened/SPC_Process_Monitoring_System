"""The nested variance structure (DATASET_GUIDE.md §4.2).

A measurement is composed from physically motivated terms rather than drawn
from one distribution. The composition is what makes the later benchmark
honest: independent Gaussian noise would make detection trivial and every
detection score meaningless (R-30).

Three properties are load-bearing and are enforced here rather than left to the
configuration author.

**Tool and chamber offsets are fixed, not resampled.** A tool mismatch is a
persistent bias, so detecting it requires comparing across tools rather than
watching one time series. Drawing a fresh offset per lot would turn a bias into
noise and delete the phenomenon.

**Fixed offsets are centred across the fleet.** Real fabs match a fleet to the
target and live with the residual mismatch between members. Centring reproduces
that, and it keeps the grand mean on target so a capability result can be read
without first subtracting an arbitrary fleet bias.

**Measurement error is separate and always present.** It is what makes Gauge
R&R meaningful: the %GRR the MSA module computes can be checked against the
sigma the generator was told to use.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from spc_platform.common.errors import SimulationConfigError
from spc_platform.domain.enums import SpatialSignature
from spc_platform.domain.ids import ParameterId, ProductId, UnitSymbol
from spc_platform.domain.specification_limit import SpecificationLimit
from spc_platform.simulation.models import ParameterPhysics, VarianceProfile
from spc_platform.simulation.seeds import derive_generator

_CP_SIGMA_SPAN = 6.0
"""Cp is defined over a six-sigma span (Montgomery §8.3)."""

_ZERO_SPREAD_TOLERANCE = 1e-12

_MIN_CARRIER_SIZE = 2
"""A one-wafer carrier has no position to have an effect."""


@dataclass(frozen=True, slots=True)
class ComponentScales:
    """Absolute sigmas for one parameter on one product, in the parameter's unit.

    ``sigma_total`` is the *random* total — lot, wafer, site, and gauge combined
    in quadrature. Tool mismatch, chamber mismatch, the slot effect, and the
    spatial signature sit outside it. That split is the point: short-term spread
    is ``sigma_total``, long-term spread includes the systematic terms, and a
    platform that reports Cp and Pp as the same number is wrong in a way this
    data will expose.
    """

    parameter_id: ParameterId
    product_id: ProductId
    unit: UnitSymbol
    target: float
    sigma_total: float
    sigma_lot: float
    sigma_wafer: float
    sigma_site: float
    sigma_gauge: float
    sigma_tool_offset: float
    sigma_chamber_offset: float
    slot_amplitude: float
    spatial_amplitude: float

    def as_dict(self) -> dict[str, float]:
        """Return the scales as plain floats, for the manifest."""
        return {
            "target": self.target,
            "sigma_total": self.sigma_total,
            "sigma_lot": self.sigma_lot,
            "sigma_wafer": self.sigma_wafer,
            "sigma_site": self.sigma_site,
            "sigma_gauge": self.sigma_gauge,
            "sigma_tool_offset": self.sigma_tool_offset,
            "sigma_chamber_offset": self.sigma_chamber_offset,
            "slot_amplitude": self.slot_amplitude,
            "spatial_amplitude": self.spatial_amplitude,
        }


def _resolve_target(physics: ParameterPhysics, spec: SpecificationLimit) -> float:
    if spec.target is not None:
        return spec.target
    if spec.lsl is not None and spec.usl is not None:
        return (spec.lsl + spec.usl) / 2.0
    raise SimulationConfigError(
        "single-sided specification carries no target, so the process has no level to sit at",
        parameter_id=str(physics.parameter_id),
        product_id=str(spec.product_id),
    )


def _resolve_sigma_total(physics: ParameterPhysics, spec: SpecificationLimit) -> float:
    if physics.sigma_total is not None:
        return physics.sigma_total
    if physics.target_cp is None:  # pragma: no cover - forbidden by model validation
        raise SimulationConfigError(
            "parameter declares neither target_cp nor sigma_total",
            parameter_id=str(physics.parameter_id),
        )
    if spec.lsl is None or spec.usl is None:
        raise SimulationConfigError(
            "target_cp needs a two-sided specification; declare sigma_total instead",
            parameter_id=str(physics.parameter_id),
            product_id=str(spec.product_id),
        )
    return (spec.usl - spec.lsl) / (_CP_SIGMA_SPAN * physics.target_cp)


def resolve_scales(
    physics: ParameterPhysics,
    profile: VarianceProfile,
    spec: SpecificationLimit,
) -> ComponentScales:
    """Turn a declared variance shape into absolute sigmas.

    The specification is the one in force at the *start* of the dataset, and is
    used only to set the scale. A specification that changes mid-window changes
    the requirement, not the process — so the physics resolved here stays fixed
    for the whole run, and a tightened limit shows up as a capability change
    with no accompanying change in the measured distribution. That is the
    behaviour the retained specification history exists to make visible.

    Parameters
    ----------
    physics
        The parameter's declared behaviour.
    profile
        The variance shape, either the parameter's own or the shared default.
    spec
        The specification in force at the dataset start.
    """
    target = _resolve_target(physics, spec)
    sigma_total = _resolve_sigma_total(physics, spec)
    lot_f, wafer_f, site_f, gauge_f = profile.random_weights.normalised()
    systematic = profile.systematic

    # A parameter with no signature has no signature amplitude, whatever the
    # profile says. Recording the profile's figure would put a number in the
    # manifest that no measurement realises, and the manifest is the ground
    # truth everything downstream is scored against.
    spatial_amplitude = (
        0.0
        if physics.spatial_signature is SpatialSignature.NONE
        else sigma_total * systematic.spatial
    )

    return ComponentScales(
        parameter_id=physics.parameter_id,
        product_id=spec.product_id,
        unit=spec.unit,
        target=target,
        sigma_total=sigma_total,
        sigma_lot=sigma_total * lot_f,
        sigma_wafer=sigma_total * wafer_f,
        sigma_site=sigma_total * site_f,
        sigma_gauge=sigma_total * gauge_f,
        sigma_tool_offset=sigma_total * systematic.tool_offset,
        sigma_chamber_offset=sigma_total * systematic.chamber_offset,
        slot_amplitude=sigma_total * systematic.slot,
        spatial_amplitude=spatial_amplitude,
    )


def fixed_offsets(
    entity_ids: tuple[str, ...],
    sigma: float,
    *,
    master_seed: int,
    stream: str,
) -> dict[str, float]:
    """Draw the persistent offsets for a set of tools or chambers.

    Drawn once per entity from a keyed stream, then centred and rescaled so the
    set has mean zero and population standard deviation ``sigma`` exactly. The
    rescaling is deliberate: these are fixed effects whose size is being
    specified, not sampled, and pinning it exactly is what lets a variance
    decomposition of the generated data be checked against the configuration.

    A single-member fleet gets a zero offset. One tool cannot mismatch itself,
    and giving it a bias would silently move the process off target.

    Parameters
    ----------
    entity_ids
        Tool or chamber identifiers, as text.
    sigma
        Intended population standard deviation of the offsets.
    master_seed
        The dataset seed.
    stream
        Stream name, distinguishing tool offsets from chamber offsets and one
        parameter's offsets from another's.
    """
    if not entity_ids:
        return {}
    if len(entity_ids) == 1 or sigma <= 0.0:
        return dict.fromkeys(entity_ids, 0.0)

    ordered = tuple(sorted(entity_ids))
    generator = derive_generator(master_seed, stream, *ordered)
    draws = generator.normal(0.0, 1.0, size=len(ordered))
    centred = draws - draws.mean()
    spread = float(np.std(centred))
    if spread <= _ZERO_SPREAD_TOLERANCE:  # pragma: no cover - vanishingly unlikely
        return dict.fromkeys(ordered, 0.0)
    scaled = centred * (sigma / spread)
    return {entity: float(value) for entity, value in zip(ordered, scaled, strict=True)}


def slot_profile(
    slots: NDArray[np.int_],
    amplitude: float,
    *,
    wafers_per_lot: int,
) -> NDArray[np.float64]:
    """Return the systematic position-in-carrier offset for the given slots.

    The shape combines a tilt across the carrier with a symmetric end-of-carrier
    effect, which is what thermal and gas-flow boundary conditions produce in a
    batch tool. It is normalised across the *whole* carrier rather than across
    the sampled slots, so a given slot carries the same offset no matter which
    slots a control plan happens to sample.

    Parameters
    ----------
    slots
        Slot numbers, 1-based.
    amplitude
        Standard deviation of the offsets across the full carrier.
    wafers_per_lot
        Carrier size, used to normalise the profile.
    """
    if amplitude <= 0.0 or wafers_per_lot < _MIN_CARRIER_SIZE:
        return np.zeros(slots.shape, dtype=np.float64)

    all_slots = np.arange(1, wafers_per_lot + 1, dtype=np.float64)
    position = (all_slots - (1.0 + wafers_per_lot) / 2.0) / ((wafers_per_lot - 1) / 2.0)
    raw = 0.5 * position + position**2
    centred = raw - raw.mean()
    spread = float(np.std(centred))
    if spread <= _ZERO_SPREAD_TOLERANCE:  # pragma: no cover - degenerate carrier
        return np.zeros(slots.shape, dtype=np.float64)
    profile = centred * (amplitude / spread)
    return np.asarray(profile[slots - 1], dtype=np.float64)
