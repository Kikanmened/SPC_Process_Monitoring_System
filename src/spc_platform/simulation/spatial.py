"""Wafer sampling plans and the systematic within-wafer signature.

This module carries more of the project's weight than its size suggests.

A generator whose within-wafer variation is independent noise would make the
rational-subgrouping question disappear: sites could be pooled into a subgroup
with no consequence, a naive implementation would pass its own benchmark, and
the resulting detection scores would be meaningless (R-04, R-30). The signature
here is *systematic* — the same shape on every wafer, up to noise — so pooling
sites absorbs it into the within-subgroup sigma, widens the limits, and stops
the chart signalling. That failure is reproducible in the generated data, which
is the only reason the platform can be shown not to commit it.

Each profile is centred over the sites of its plan, so the signature moves the
site values relative to one another without moving the wafer mean. A wafer-mean
chart is therefore blind to it by construction, and a wafer map is not — which
is the physical situation these patterns are modelled on.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from spc_platform.common.errors import SimulationConfigError
from spc_platform.domain.enums import SpatialSignature

WAFER_RADIUS_MM = 150.0
"""Nominal 300 mm wafer radius."""

EDGE_EXCLUSION_MM = 3.0
"""Ring at the wafer edge that carries no measurable die."""

USABLE_RADIUS_MM = WAFER_RADIUS_MM - EDGE_EXCLUSION_MM

_EDGE_ONSET = 0.78
"""Normalised radius at which the edge signature turns on."""

_EDGE_WIDTH = 0.06
"""Width of the edge transition, as a fraction of the usable radius."""

_ZERO_SPREAD_TOLERANCE = 1e-12

_COORDINATE_DECIMALS = 6
"""Site coordinates are exact to the nanometre; below that is float noise."""

# Each plan is the centre site followed by rings of (radius mm, count, phase deg).
# Site 1 is always the centre, and sites then run ring by ring with the angle
# ascending, so a site_id means the same location in every dataset.
_PLAN_RINGS: dict[int, tuple[tuple[float, int, float], ...]] = {
    1: (),
    5: ((110.0, 4, 0.0),),
    9: ((75.0, 4, 0.0), (125.0, 4, 45.0)),
    13: ((60.0, 4, 0.0), (105.0, 4, 45.0), (140.0, 4, 22.5)),
}

SUPPORTED_SITE_COUNTS = tuple(sorted(_PLAN_RINGS))


def sampling_plan(site_count: int) -> NDArray[np.float64]:
    """Return the site coordinates for a plan, in millimetres from wafer centre.

    Parameters
    ----------
    site_count
        Number of measurement sites. One of :data:`SUPPORTED_SITE_COUNTS`.

    Returns
    -------
    numpy.ndarray
        Array of shape ``(site_count, 2)`` holding ``(x, y)`` in millimetres.

    Raises
    ------
    SimulationConfigError
        If no plan is defined for ``site_count``. Interpolating an undeclared
        plan would put sites at coordinates no metrology recipe visits.
    """
    rings = _PLAN_RINGS.get(site_count)
    if rings is None:
        raise SimulationConfigError(
            "no sampling plan defined for this site count",
            site_count=site_count,
            supported=list(SUPPORTED_SITE_COUNTS),
        )

    coordinates = [(0.0, 0.0)]
    for radius, count, phase_degrees in rings:
        for index in range(count):
            angle = np.deg2rad(phase_degrees + index * (360.0 / count))
            # Rounded to the nanometre. Without it a site nominally on an axis
            # lands at 4.6e-15 mm from it, which is arithmetically harmless and
            # reads as a defect in every wafer map and CSV export.
            coordinates.append(
                (
                    round(radius * float(np.cos(angle)), _COORDINATE_DECIMALS),
                    round(radius * float(np.sin(angle)), _COORDINATE_DECIMALS),
                )
            )

    plan = np.asarray(coordinates, dtype=np.float64)
    if plan.shape[0] != site_count:
        raise SimulationConfigError(
            "sampling plan ring definition does not match its site count",
            site_count=site_count,
            produced=plan.shape[0],
        )
    return plan


def _raw_profile(
    kind: SpatialSignature,
    coordinates: NDArray[np.float64],
) -> NDArray[np.float64]:
    """Return the unscaled shape of a signature at the given coordinates."""
    x = coordinates[:, 0]
    y = coordinates[:, 1]
    normalised_radius = np.hypot(x, y) / USABLE_RADIUS_MM

    match kind:
        case SpatialSignature.NONE:
            return np.zeros(coordinates.shape[0], dtype=np.float64)
        case SpatialSignature.RADIAL:
            # Centre-to-edge curvature: deposition and etch rate both vary with
            # radius, and the resulting profile is quadratic to first order.
            return np.asarray(normalised_radius**2, dtype=np.float64)
        case SpatialSignature.EDGE:
            # Flat across the wafer until the outermost ring, where edge effects
            # turn on sharply. A radial fit will not represent this.
            return np.asarray(
                1.0 / (1.0 + np.exp(-(normalised_radius - _EDGE_ONSET) / _EDGE_WIDTH)),
                dtype=np.float64,
            )
        case SpatialSignature.ASYMMETRIC:
            # A one-sided tilt, as produced by a gas-flow or chuck-contact
            # asymmetry. Rotationally symmetric statistics are blind to it.
            return np.asarray(x / USABLE_RADIUS_MM, dtype=np.float64)


def signature_profile(
    kind: SpatialSignature,
    coordinates: NDArray[np.float64],
    amplitude: float,
) -> NDArray[np.float64]:
    """Return the per-site offset imposed by a spatial signature.

    The profile is centred and scaled to a standard deviation of ``amplitude``
    across the sites of the plan. Centring is what keeps the signature invisible
    to the wafer mean; scaling is what makes ``amplitude`` mean the same thing
    for every parameter regardless of its unit.

    Parameters
    ----------
    kind
        Which signature to impose.
    coordinates
        Site coordinates from :func:`sampling_plan`, shape ``(n_sites, 2)``.
    amplitude
        Standard deviation of the returned offsets across sites, in the
        parameter's unit.

    Returns
    -------
    numpy.ndarray
        Offsets of shape ``(n_sites,)``, summing to zero. A single-site plan and
        the ``NONE`` signature both return zeros — there is no within-wafer
        shape to impose in either case.
    """
    raw = _raw_profile(kind, coordinates)
    centred = raw - raw.mean()
    spread = float(np.std(centred))
    if spread <= _ZERO_SPREAD_TOLERANCE:
        return np.zeros_like(centred)
    return np.asarray(centred * (amplitude / spread), dtype=np.float64)
