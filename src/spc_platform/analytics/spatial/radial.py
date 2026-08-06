"""Radial (centre-to-edge) signature statistic.

A deposition or etch rate that varies with radius produces a bowl or a dome.
The first-order shape is quadratic in radius; the statistic here is the
correlation of the centred field with that geometric predictor.
"""

from __future__ import annotations

import numpy as np

from spc_platform.analytics.spatial._correlation import absolute_correlation
from spc_platform.analytics.spatial.field import WAFER_RADIUS_MM, WaferField
from spc_platform.common.types import FloatArray


def radial_predictor(field: WaferField) -> FloatArray:
    """Centred squared normalised radius at each site."""
    normalised = field.radii / WAFER_RADIUS_MM
    predictor = normalised**2
    centred: FloatArray = predictor - float(np.mean(predictor))
    return centred


def radial_score(field: WaferField) -> float:
    """Absolute correlation of the centred field with squared radius.

    Returns
    -------
    float
        In ``[0, 1]``. Zero when either side has no variation.
    """
    return absolute_correlation(field.centred_values, radial_predictor(field))
