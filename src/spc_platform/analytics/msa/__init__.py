"""Measurement system analysis (FR-M01 - FR-M04).

Not a side report. Every chart in this platform plots the process and the gauge
added together, so how much of a chart is gauge is the precondition for reading
any of it.
"""

from spc_platform.analytics.msa.acceptance import (
    AcceptanceBands,
    GaugeCriterion,
    GaugeJudgement,
    GaugeVerdict,
    judge,
)
from spc_platform.analytics.msa.bias_linearity import (
    DEFAULT_SIGNIFICANCE,
    MIN_BIAS_MEASUREMENTS,
    MIN_LINEARITY_LEVELS,
    BiasResult,
    LinearityResult,
    bias,
    linearity,
)
from spc_platform.analytics.msa.gauge_rr import (
    DEFAULT_POOLING_SIGNIFICANCE,
    DEFAULT_STUDY_VARIATION_MULTIPLIER,
    MIN_OPERATORS,
    MIN_PARTS,
    MIN_REPLICATES,
    NDC_MULTIPLIER,
    AnovaTable,
    AnovaTerm,
    GaugeRRResult,
    GaugeStudy,
    VarianceComponents,
    VarianceSource,
    anova_table,
    gauge_rr_anova,
)
from spc_platform.analytics.msa.stability import (
    MIN_STABILITY_MEASUREMENTS,
    StabilityResult,
    stability,
)

__all__ = [
    "DEFAULT_POOLING_SIGNIFICANCE",
    "DEFAULT_SIGNIFICANCE",
    "DEFAULT_STUDY_VARIATION_MULTIPLIER",
    "MIN_BIAS_MEASUREMENTS",
    "MIN_LINEARITY_LEVELS",
    "MIN_OPERATORS",
    "MIN_PARTS",
    "MIN_REPLICATES",
    "MIN_STABILITY_MEASUREMENTS",
    "NDC_MULTIPLIER",
    "AcceptanceBands",
    "AnovaTable",
    "AnovaTerm",
    "BiasResult",
    "GaugeCriterion",
    "GaugeJudgement",
    "GaugeRRResult",
    "GaugeStudy",
    "GaugeVerdict",
    "LinearityResult",
    "StabilityResult",
    "VarianceComponents",
    "VarianceSource",
    "anova_table",
    "bias",
    "gauge_rr_anova",
    "judge",
    "linearity",
    "stability",
]
