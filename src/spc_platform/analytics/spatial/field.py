"""A wafer's site measurements as a single field the classifier can read.

Coordinates are millimetres from wafer centre. Values are in the measurement's
own unit. The two arrays travel together so a caller cannot pair one wafer's
coordinates with another's values — the shape check here is the whole of the
safety the rest of the package relies on.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spc_platform.common.errors import InsufficientSitesError
from spc_platform.common.types import FloatArray, FloatMatrix

MIN_SITES_FOR_SIGNATURE = 9
"""Fewer than nine sites cannot separate a radial bowl from an edge ring.

A five-site cross puts every non-centre site on a single radius, so the radial
and edge predictors are the same vector and the classifier cannot tell them
apart. It also overfits noise: roughly one wafer in three of pure noise clears
a 0.75 correlation on five sites. Nine sites — a centre plus two rings — is
the smallest plan that gives the two radial patterns different shapes and keeps
the false-positive rate on unstructured wafers below five percent.
"""

WAFER_RADIUS_MM = 150.0
"""Nominal radius of a 300 mm wafer."""

_SITE_AXES = 2
"""A coordinate array is a rectangle: sites down, (x, y) across."""


@dataclass(frozen=True, slots=True)
class WaferField:
    """Site coordinates and their measured values on one wafer.

    Attributes
    ----------
    coordinates
        Shape ``(n_sites, 2)`` holding ``(x, y)`` in millimetres from centre.
    values
        One measurement per site, in the parameter's unit.
    """

    coordinates: FloatMatrix
    values: FloatArray

    def __post_init__(self) -> None:
        """Reject a field that is empty, mismatched, or below the site minimum."""
        coords = np.asarray(self.coordinates, dtype=np.float64)
        vals = np.asarray(self.values, dtype=np.float64)
        if coords.ndim != _SITE_AXES or coords.shape[1] != _SITE_AXES:
            raise InsufficientSitesError(
                "site coordinates must be an (n, 2) array of (x, y) in millimetres",
                shape=coords.shape,
            )
        if vals.ndim != 1 or vals.shape[0] != coords.shape[0]:
            raise InsufficientSitesError(
                "values must be one measurement per site",
                sites=int(coords.shape[0]),
                values=int(vals.shape[0]),
            )
        if coords.shape[0] < MIN_SITES_FOR_SIGNATURE:
            raise InsufficientSitesError(
                "too few sites to classify a spatial signature",
                sites=int(coords.shape[0]),
                required=MIN_SITES_FOR_SIGNATURE,
            )
        object.__setattr__(self, "coordinates", coords)
        object.__setattr__(self, "values", vals)

    @property
    def n_sites(self) -> int:
        """Number of measurement sites on the wafer."""
        return int(self.values.size)

    @property
    def radii(self) -> FloatArray:
        """Distance of each site from wafer centre, in millimetres."""
        radii: FloatArray = np.hypot(self.coordinates[:, 0], self.coordinates[:, 1])
        return radii

    @property
    def centred_values(self) -> FloatArray:
        """Values with the wafer mean removed.

        Spatial signatures are shapes within a wafer. Removing the mean keeps
        the classifier from mistaking a level shift for a pattern.
        """
        centred: FloatArray = self.values - float(np.mean(self.values))
        return centred
