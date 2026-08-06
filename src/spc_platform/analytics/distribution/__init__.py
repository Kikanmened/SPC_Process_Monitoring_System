"""Distributional assessment: is the normal assumption safe, and if not, what then.

Sits below :mod:`spc_platform.analytics.capability` in the module graph, because
capability needs to know the shape of the distribution and the shape of the
distribution does not need to know about capability.
"""

from spc_platform.analytics.distribution.normality import (
    DEFAULT_SIGNIFICANCE,
    MIN_NORMALITY_OBSERVATIONS,
    MIN_TRANSFORM_OBSERVATIONS,
    NATURAL_TOLERANCE_QUANTILES,
    CapabilityMethod,
    NaturalTolerance,
    NormalityAssessment,
    assess_normality,
    natural_tolerance,
)

__all__ = [
    "DEFAULT_SIGNIFICANCE",
    "MIN_NORMALITY_OBSERVATIONS",
    "MIN_TRANSFORM_OBSERVATIONS",
    "NATURAL_TOLERANCE_QUANTILES",
    "CapabilityMethod",
    "NaturalTolerance",
    "NormalityAssessment",
    "assess_normality",
    "natural_tolerance",
]
