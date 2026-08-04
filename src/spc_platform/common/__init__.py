"""Common: cross-cutting primitives shared by every layer.

Units, time handling, provenance, and the ``SPCPlatformError`` hierarchy.
Reachable from ``analytics`` and therefore subject to the same purity rule: no
I/O, no clocks read implicitly, no framework dependencies.
"""

from spc_platform.common.errors import (
    AuditWriteError,
    ConfigurationError,
    DegenerateSeriesError,
    InsufficientDataError,
    NaiveDatetimeError,
    NoActiveBaselineError,
    SchemaValidationError,
    SPCPlatformError,
    UnauthorisedActionError,
    UnknownUnitError,
    UnstableProcessError,
)
from spc_platform.common.provenance import Provenance, capture_provenance
from spc_platform.common.time import Clock, FixedClock, SystemClock, require_aware
from spc_platform.common.types import FloatArray
from spc_platform.common.units import UnitConversion, UnitRegistry, registry_from_declarations

__all__ = [
    "AuditWriteError",
    "Clock",
    "ConfigurationError",
    "DegenerateSeriesError",
    "FixedClock",
    "FloatArray",
    "InsufficientDataError",
    "NaiveDatetimeError",
    "NoActiveBaselineError",
    "Provenance",
    "SPCPlatformError",
    "SchemaValidationError",
    "SystemClock",
    "UnauthorisedActionError",
    "UnitConversion",
    "UnitRegistry",
    "UnknownUnitError",
    "UnstableProcessError",
    "capture_provenance",
    "registry_from_declarations",
    "require_aware",
]
