"""Asymmetric (left-right / front-back tilt) signature statistic.

A gas-flow or chuck-contact asymmetry tilts the wafer field along one axis. The
statistic is the *adjusted* multiple correlation of the centred field with the
site coordinates — the R of the best-fitting plane, penalised for the two
degrees of freedom the plane spends. Without the adjustment a five-site wafer
of pure noise routinely clears 0.75, and the classifier invents a tilt (R-43).
"""

from __future__ import annotations

from math import sqrt

import numpy as np

from spc_platform.analytics.spatial._correlation import absolute_correlation
from spc_platform.analytics.spatial.field import WaferField
from spc_platform.common.types import FloatArray

_PLANE_PARAMETERS = 2
"""A tilt is a plane: two slopes, no intercept (the field is already centred)."""


def asymmetry_predictor(field: WaferField) -> FloatArray:
    """Best linear combination of ``x`` and ``y`` matching the centred field."""
    design = np.column_stack(
        (
            field.coordinates[:, 0] - float(np.mean(field.coordinates[:, 0])),
            field.coordinates[:, 1] - float(np.mean(field.coordinates[:, 1])),
        )
    )
    target = field.centred_values
    coefficients, _, rank, _ = np.linalg.lstsq(design, target, rcond=None)
    if rank == 0:
        return np.zeros(field.n_sites, dtype=np.float64)
    predicted: FloatArray = design @ coefficients
    return predicted


def asymmetry_score(field: WaferField) -> float:
    """Return the adjusted multiple correlation of the field with its best plane.

    Returns
    -------
    float
        In ``[0, 1]``. Zero when the sites give the plane nothing to fit, when
        the field is flat, or when the unadjusted fit is no better than chance
        after penalising for two fitted slopes.
    """
    correlation = absolute_correlation(field.centred_values, asymmetry_predictor(field))
    return _adjusted_correlation(correlation, field.n_sites, _PLANE_PARAMETERS)


def _adjusted_correlation(correlation: float, n_sites: int, parameters: int) -> float:
    """Convert a multiple correlation to its degrees-of-freedom-adjusted form."""
    degrees = n_sites - parameters - 1
    if degrees <= 0:
        return 0.0
    r_squared = correlation**2
    adjusted = 1.0 - (1.0 - r_squared) * (n_sites - 1) / degrees
    if adjusted <= 0.0:
        return 0.0
    return sqrt(adjusted)
