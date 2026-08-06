"""Shared correlation helper for the three signature statistics."""

from __future__ import annotations

import numpy as np

from spc_platform.common.types import FloatArray


def absolute_correlation(left: FloatArray, right: FloatArray) -> float:
    """Pearson correlation magnitude, or zero when either side is constant."""
    if float(np.std(left)) == 0.0 or float(np.std(right)) == 0.0:
        return 0.0
    matrix = np.corrcoef(left, right)
    return abs(float(matrix[0, 1]))
