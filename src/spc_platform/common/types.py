"""Shared numerical type aliases.

Identifier NewTypes live in ``spc_platform.domain.ids`` — they are fab
vocabulary, not cross-cutting primitives. This module holds only what the
numerical layers need to share without importing analytics.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
"""A one-dimensional float64 array — the currency of the analytics layer."""
