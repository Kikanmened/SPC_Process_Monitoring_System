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

FloatMatrix = npt.NDArray[np.float64]
"""A two-dimensional float64 array, one row per subgroup.

Identical to :data:`FloatArray` as far as the type checker is concerned, since
NumPy does not encode rank in its types. It is a separate name so that a
signature states which shape it expects, which is the part a reader gets wrong.
"""

IntArray = npt.NDArray[np.int_]
"""Counts and sizes — defectives, opportunities, and unequal subgroup sizes."""

BoolArray = npt.NDArray[np.bool_]
"""One flag per plotted point — which points a rule signalled on."""
