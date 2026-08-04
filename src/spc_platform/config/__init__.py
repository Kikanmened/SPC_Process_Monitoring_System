"""Configuration: layered YAML parsed once into immutable typed models.

No module elsewhere reads YAML or an environment variable. An unknown
configuration key is an error, not a silently ignored typo
(SYSTEM_ARCHITECTURE.md §3.6, FR-CF02).
"""

from spc_platform.config.profiles import Profile
from spc_platform.config.reference import (
    ControlPlan,
    ControlPlanCharacteristic,
    ReferenceData,
    ToolRecord,
    load_reference_data,
)
from spc_platform.config.revision import compute_config_revision
from spc_platform.config.settings import Settings, load_settings

__all__ = [
    "ControlPlan",
    "ControlPlanCharacteristic",
    "Profile",
    "ReferenceData",
    "Settings",
    "ToolRecord",
    "compute_config_revision",
    "load_reference_data",
    "load_settings",
]
