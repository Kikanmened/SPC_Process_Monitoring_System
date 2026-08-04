"""Domain layer: the vocabulary of wafer fabrication as types.

Imports nothing from this repository, and no third-party library beyond the
standard library and Pydantic for value validation
(SYSTEM_ARCHITECTURE.md §2, rule 1).
"""

from spc_platform.domain.baseline import Baseline
from spc_platform.domain.chart_spec import ChartSpec, RuleDefinition, RuleSet
from spc_platform.domain.control_limit import ControlLimit
from spc_platform.domain.disposition import Disposition
from spc_platform.domain.enums import (
    BaselineStatus,
    ChartType,
    DispositionAction,
    EquipmentState,
    MeasurementStatus,
    SigmaEstimator,
    SubgroupingKind,
    ViolationSeverity,
)
from spc_platform.domain.equipment import Chamber, ProcessStep, Recipe, Tool
from spc_platform.domain.errors import DomainError, DomainInvariantError
from spc_platform.domain.ids import (
    ActorId,
    BaselineId,
    ChamberId,
    CodeRevision,
    ConfigRevision,
    DataRevision,
    LotId,
    MeasurementId,
    MetrologyToolId,
    OcapId,
    ParameterId,
    ProductId,
    RecipeId,
    RuleId,
    SiteId,
    StepId,
    ToolId,
    UnitSymbol,
    WaferId,
)
from spc_platform.domain.material import Lot, Site, Wafer
from spc_platform.domain.measurement import Measurement
from spc_platform.domain.measurement_series import MeasurementSeries
from spc_platform.domain.parameter import Parameter
from spc_platform.domain.specification_limit import SpecificationLimit
from spc_platform.domain.subgrouping import Subgroup, SubgroupingStrategy
from spc_platform.domain.violation import Violation

__all__ = [
    "ActorId",
    "Baseline",
    "BaselineId",
    "BaselineStatus",
    "Chamber",
    "ChamberId",
    "ChartSpec",
    "ChartType",
    "CodeRevision",
    "ConfigRevision",
    "ControlLimit",
    "DataRevision",
    "Disposition",
    "DispositionAction",
    "DomainError",
    "DomainInvariantError",
    "EquipmentState",
    "Lot",
    "LotId",
    "Measurement",
    "MeasurementId",
    "MeasurementSeries",
    "MeasurementStatus",
    "MetrologyToolId",
    "OcapId",
    "Parameter",
    "ParameterId",
    "ProcessStep",
    "ProductId",
    "Recipe",
    "RecipeId",
    "RuleDefinition",
    "RuleId",
    "RuleSet",
    "SigmaEstimator",
    "Site",
    "SiteId",
    "SpecificationLimit",
    "StepId",
    "Subgroup",
    "SubgroupingKind",
    "SubgroupingStrategy",
    "Tool",
    "ToolId",
    "UnitSymbol",
    "Violation",
    "ViolationSeverity",
    "Wafer",
    "WaferId",
]
