"""Chart constants and dispersion estimators — the bottom of the analytics layer.

Imports no other analytics package, so a wrong constant here has exactly one
place to be wrong and one set of reference tests guarding it.
"""

from spc_platform.analytics.estimators.constants import (
    MAX_TABULATED_SUBGROUP_SIZE,
    MIN_SUBGROUP_SIZE,
    a2,
    a3,
    b3,
    b4,
    c4,
    d2,
    d3,
    d3_lower,
    d4_upper,
    e2,
    normal_quantile,
    two_sided_exceedance,
)
from spc_platform.analytics.estimators.sigma import (
    MOVING_RANGE_SPAN,
    SigmaEstimate,
    moving_ranges,
    sigma_overall,
    sigma_within_moving_range,
    sigma_within_range,
    sigma_within_stdev,
    subgroup_ranges,
    subgroup_stdevs,
)

__all__ = [
    "MAX_TABULATED_SUBGROUP_SIZE",
    "MIN_SUBGROUP_SIZE",
    "MOVING_RANGE_SPAN",
    "SigmaEstimate",
    "a2",
    "a3",
    "b3",
    "b4",
    "c4",
    "d2",
    "d3",
    "d3_lower",
    "d4_upper",
    "e2",
    "moving_ranges",
    "normal_quantile",
    "sigma_overall",
    "sigma_within_moving_range",
    "sigma_within_range",
    "sigma_within_stdev",
    "subgroup_ranges",
    "subgroup_stdevs",
    "two_sided_exceedance",
]
