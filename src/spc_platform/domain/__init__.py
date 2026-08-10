"""Domain layer: the vocabulary of wafer fabrication as types.

Imports nothing from this repository, and no third-party library beyond the
standard library and Pydantic for value validation
(SYSTEM_ARCHITECTURE.md §2, rule 1).
"""

from spc_platform.domain.baseline import Baseline
from spc_platform.domain.chart_spec import ChartSpec, RuleDefinition, RuleSet
from spc_platform.domain.charting import (
    ChartLimits,
    ChartPanel,
    ControlChart,
    PlottedSeries,
)
from spc_platform.domain.control_limit import ControlLimit
from spc_platform.domain.disposition import Disposition
from spc_platform.domain.enums import (
    BaselineStatus,
    ChartStatistic,
    ChartType,
    DispositionAction,
    EquipmentState,
    ExcursionState,
    MeasurementStatus,
    ReportType,
    SigmaEstimator,
    SpatialSignature,
    SubgroupingKind,
    ViolationSeverity,
)
from spc_platform.domain.equipment import Chamber, ProcessStep, Recipe, Tool
from spc_platform.domain.errors import (
    DispositionRequiredError,
    DomainError,
    DomainInvariantError,
    UnknownDispositionError,
)
from spc_platform.domain.excursion import Excursion
from spc_platform.domain.ids import (
    ActorId,
    BaselineId,
    CapaId,
    ChamberId,
    CodeRevision,
    ConfigRevision,
    DataRevision,
    EightDId,
    ExcursionId,
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
from spc_platform.domain.lineage import IngestionRunRecord
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
    "CapaId",
    "Chamber",
    "ChamberId",
    "ChartLimits",
    "ChartPanel",
    "ChartSpec",
    "ChartStatistic",
    "ChartType",
    "CodeRevision",
    "ConfigRevision",
    "ControlChart",
    "ControlLimit",
    "DataRevision",
    "Disposition",
    "DispositionAction",
    "DispositionRequiredError",
    "DomainError",
    "DomainInvariantError",
    "EightDId",
    "EquipmentState",
    "Excursion",
    "ExcursionId",
    "ExcursionState",
    "IngestionRunRecord",
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
    "PlottedSeries",
    "ProcessStep",
    "ProductId",
    "Recipe",
    "RecipeId",
    "ReportType",
    "RuleDefinition",
    "RuleId",
    "RuleSet",
    "SigmaEstimator",
    "Site",
    "SiteId",
    "SpatialSignature",
    "SpecificationLimit",
    "StepId",
    "Subgroup",
    "SubgroupingKind",
    "SubgroupingStrategy",
    "Tool",
    "ToolId",
    "UnitSymbol",
    "UnknownDispositionError",
    "Violation",
    "ViolationSeverity",
    "Wafer",
    "WaferId",
]
