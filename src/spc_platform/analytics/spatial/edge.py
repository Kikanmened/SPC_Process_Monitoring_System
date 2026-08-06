"""Edge-ring signature statistic.

Edge effects sit flat across the wafer until the outermost sites, where they
turn on sharply. A pure correlation with an outer-ring indicator is still
confounded with a radial bowl — the outer sites are also the ones with the
largest radius — so the statistic here is the partial correlation of the
centred field with the outer-ring indicator *after* the radial predictor has
been removed. A bowl then scores near zero; a step at the edge does not.

The indicator is deliberately a step, not a smooth transition. Sharing the
generator's sigmoid parameters would make the classifier confirm the data it
is meant to discover (ADR-0021).
"""

from __future__ import annotations

import numpy as np

from spc_platform.analytics.spatial._correlation import absolute_correlation
from spc_platform.analytics.spatial.field import WaferField
from spc_platform.analytics.spatial.radial import radial_predictor
from spc_platform.common.types import FloatArray

_OUTER_FRACTION = 0.85
"""Sites beyond this fraction of the plan's outermost radius are the edge ring.

Relative to the plan, not the wafer blank: a five-site cross has its outer
sites at ~110 mm on a 150 mm wafer, and those are the edge for that plan.
"""


def edge_predictor(field: WaferField) -> FloatArray:
    """Centred indicator that is one on the outermost sites and zero elsewhere."""
    radii = field.radii
    outer = float(np.max(radii))
    if outer <= 0.0:
        return np.zeros(field.n_sites, dtype=np.float64)
    indicator = (radii >= _OUTER_FRACTION * outer).astype(np.float64)
    centred: FloatArray = indicator - float(np.mean(indicator))
    return centred


def edge_score(field: WaferField) -> float:
    """Partial correlation of the field with the outer ring, radial removed.

    Returns
    -------
    float
        In ``[0, 1]``. Zero when the plan has no distinct outer ring, when the
        field is flat, or when everything the outer ring explains is already
        explained by a radial bowl.
    """
    values = _residualize(field.centred_values, radial_predictor(field))
    edge = _residualize(edge_predictor(field), radial_predictor(field))
    return absolute_correlation(values, edge)


def _residualize(target: FloatArray, covariate: FloatArray) -> FloatArray:
    """Remove the linear projection of ``covariate`` from ``target``."""
    if float(np.std(covariate)) == 0.0:
        return target
    slope = float(np.dot(target, covariate) / np.dot(covariate, covariate))
    residual: FloatArray = target - slope * covariate
    return residual
