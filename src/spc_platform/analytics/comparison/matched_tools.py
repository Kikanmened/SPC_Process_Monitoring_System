"""Two-group comparison for matched parameters across tools or chambers (FR-T01).

Welch's t-test is used when both groups have at least two observations: it does
not assume equal variances, which parallel tools rarely have. The result states
the test name, degrees of freedom, and a simple mean-difference effect size so
the engineer can judge strength rather than receive a cause verdict.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from spc_platform.common.errors import InsufficientDataError
from spc_platform.common.types import FloatArray

TEST_NAME = "welch_t"
"""Named so the UI never shows an anonymous p-value (FR-T01)."""

MIN_GROUP_SIZE = 2
"""Welch's t-test needs at least two observations per group."""


@dataclass(frozen=True, slots=True)
class MatchedGroupComparison:
    """Outcome of comparing two matched series."""

    test_name: str
    statistic: float
    p_value: float
    degrees_of_freedom: float
    mean_a: float
    mean_b: float
    effect_size: float
    n_a: int
    n_b: int


def compare_two_groups(group_a: FloatArray, group_b: FloatArray) -> MatchedGroupComparison:
    """Compare two independent samples with Welch's t-test.

    Parameters
    ----------
    group_a, group_b
        Observations for each tool or chamber, same unit.

    Raises
    ------
    InsufficientDataError
        If either group has fewer than two observations.
    """
    a = np.asarray(group_a, dtype=np.float64).ravel()
    b = np.asarray(group_b, dtype=np.float64).ravel()
    if a.size < MIN_GROUP_SIZE or b.size < MIN_GROUP_SIZE:
        raise InsufficientDataError(
            "Welch's t-test needs at least two observations in each group",
            n_a=int(a.size),
            n_b=int(b.size),
            required=MIN_GROUP_SIZE,
        )
    result = stats.ttest_ind(a, b, equal_var=False, alternative="two-sided")
    mean_a = float(np.mean(a))
    mean_b = float(np.mean(b))
    pooled = float(np.sqrt(0.5 * (np.var(a, ddof=1) + np.var(b, ddof=1))))
    effect = 0.0 if pooled == 0.0 else (mean_a - mean_b) / pooled
    return MatchedGroupComparison(
        test_name=TEST_NAME,
        statistic=float(result.statistic),
        p_value=float(result.pvalue),
        degrees_of_freedom=float(result.df),
        mean_a=mean_a,
        mean_b=mean_b,
        effect_size=effect,
        n_a=int(a.size),
        n_b=int(b.size),
    )
