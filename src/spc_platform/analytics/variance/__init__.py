"""Variance decomposition (Module 7, FR-S07).

Splitting a total sigma into the levels of the sampling hierarchy — lot, wafer,
and within-wafer — so that an investigation starts at the level where the
variation actually lives.
"""

from spc_platform.analytics.variance.nested import (
    HENDERSON_METHOD_I,
    LOT_WAFER_SITE,
    LOT_WAFER_SITE_MODEL,
    MIN_LEVELS,
    NestedComponent,
    NestedMeasurements,
    NestedTerm,
    NestedVarianceResult,
    VarianceModel,
    decompose_variance,
)

__all__ = [
    "HENDERSON_METHOD_I",
    "LOT_WAFER_SITE",
    "LOT_WAFER_SITE_MODEL",
    "MIN_LEVELS",
    "NestedComponent",
    "NestedMeasurements",
    "NestedTerm",
    "NestedVarianceResult",
    "VarianceModel",
    "decompose_variance",
]
