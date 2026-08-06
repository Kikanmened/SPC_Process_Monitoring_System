"""Wafer spatial signature classification (Module 6, FR-S02).

Radial, edge, asymmetric, or none — with none as the default outcome rather
than the residual left when nothing else fits.
"""

from spc_platform.analytics.spatial.field import (
    MIN_SITES_FOR_SIGNATURE,
    WAFER_RADIUS_MM,
    WaferField,
)
from spc_platform.analytics.spatial.signature import (
    DEFAULT_MINIMUM_SCORE,
    SignatureClassification,
    SignaturePolicy,
    classify_spatial_signature,
)

__all__ = [
    "DEFAULT_MINIMUM_SCORE",
    "MIN_SITES_FOR_SIGNATURE",
    "WAFER_RADIUS_MM",
    "SignatureClassification",
    "SignaturePolicy",
    "WaferField",
    "classify_spatial_signature",
]
