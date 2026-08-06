"""The fab the generator runs, derived from committed reference data.

Nothing here invents a tool, a chamber, or a specification. The topology is
read out of ``data/reference/`` and cross-checked against the generator
configuration, because two sources of truth for a tool identifier would let the
generator emit measurements the pipeline then rejects as referencing equipment
that does not exist — a failure that surfaces late and reads like a pipeline
bug.

The control plan is also the sampling authority: how many wafers are measured
and how often comes from ``control_plans.yaml``, so a dataset cannot be sampled
differently from the plan it will be charted against.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from spc_platform.common.errors import SimulationConfigError
from spc_platform.config.reference import ControlPlanCharacteristic, ReferenceData
from spc_platform.domain.enums import ChartType
from spc_platform.domain.ids import (
    ChamberId,
    MetrologyToolId,
    ParameterId,
    ProductId,
    RecipeId,
    StepId,
    ToolId,
)
from spc_platform.domain.parameter import Parameter
from spc_platform.domain.specification_limit import SpecificationLimit
from spc_platform.simulation.models import GeneratorConfig
from spc_platform.simulation.spatial import SUPPORTED_SITE_COUNTS

FREQUENCY_INTERVALS: Mapping[str, int] = {
    "every_lot": 1,
    "every_2nd_lot": 2,
    "every_5th_lot": 5,
}
"""Control-plan sampling frequencies, as an interval in lots."""

SpecificationKey = tuple[ParameterId, ProductId, StepId]


def recipe_for(step_id: StepId, product_id: ProductId) -> RecipeId:
    """Return the recipe a product runs at a step.

    One recipe per step and product is a simplification of a real route, and a
    deliberate one: recipe-level variation is not something this release
    analyses, and modelling it would add a dimension nothing consumes.
    """
    return RecipeId(f"RCP-{step_id}-{product_id}")


@dataclass(frozen=True, slots=True)
class Characteristic:
    """One charted characteristic, with everything needed to generate it."""

    parameter: Parameter
    product_id: ProductId
    step_id: StepId
    chart_type: ChartType
    sample_size: int
    lot_interval: int

    @property
    def parameter_id(self) -> ParameterId:
        """The parameter this characteristic charts."""
        return self.parameter.parameter_id

    def is_due(self, lot_index: int) -> bool:
        """Whether this characteristic is measured on the lot at ``lot_index``."""
        return lot_index % self.lot_interval == 0


@dataclass(frozen=True, slots=True)
class Topology:
    """The resolved fab model: equipment, characteristics, and specifications."""

    tools_by_step: Mapping[StepId, tuple[ToolId, ...]]
    chambers_by_tool: Mapping[ToolId, tuple[ChamberId, ...]]
    gauges_by_method: Mapping[str, tuple[MetrologyToolId, ...]]
    characteristics_by_product: Mapping[ProductId, tuple[Characteristic, ...]]
    specifications: Mapping[SpecificationKey, tuple[SpecificationLimit, ...]]
    step_positions: Mapping[StepId, int]
    """Position of each step in the route, so measurements fall in route order."""

    def specification_at(self, key: SpecificationKey, at: datetime) -> SpecificationLimit:
        """Return the specification in force for ``key`` at the instant ``at``.

        Raises
        ------
        SimulationConfigError
            If no limit is in force, or if more than one is. Overlapping
            effective windows mean the reference data cannot answer "what was
            the limit in March", which is the question the effective dates exist
            to answer.
        """
        candidates = [limit for limit in self.specifications.get(key, ()) if _in_force(limit, at)]
        if not candidates:
            raise SimulationConfigError(
                "no specification limit in force",
                parameter_id=str(key[0]),
                product_id=str(key[1]),
                step_id=str(key[2]),
                at=at.isoformat(),
            )
        if len(candidates) > 1:
            raise SimulationConfigError(
                "specification limits overlap in time",
                parameter_id=str(key[0]),
                product_id=str(key[1]),
                step_id=str(key[2]),
                at=at.isoformat(),
                count=len(candidates),
            )
        return candidates[0]

    def gauges_for(self, method: str) -> tuple[MetrologyToolId, ...]:
        """Return the gauges that perform a metrology method."""
        pool = self.gauges_by_method.get(method)
        if not pool:
            raise SimulationConfigError("no gauge pool for metrology method", method=method)
        return pool


def _in_force(limit: SpecificationLimit, at: datetime) -> bool:
    if at < limit.effective_from:
        return False
    return limit.effective_to is None or at < limit.effective_to


def _build_equipment(
    reference: ReferenceData,
) -> tuple[dict[StepId, tuple[ToolId, ...]], dict[ToolId, tuple[ChamberId, ...]]]:
    tools_by_step: dict[StepId, list[ToolId]] = {}
    chambers_by_tool: dict[ToolId, tuple[ChamberId, ...]] = {}
    for record in reference.tools:
        if record.tool.is_metrology:
            continue
        tools_by_step.setdefault(record.tool.step_id, []).append(record.tool.tool_id)
        chambers_by_tool[record.tool.tool_id] = tuple(
            chamber.chamber_id for chamber in record.chambers
        )
    return (
        {step: tuple(sorted(tools)) for step, tools in tools_by_step.items()},
        chambers_by_tool,
    )


def _validate_gauge_pools(
    reference: ReferenceData,
    config: GeneratorConfig,
) -> dict[str, tuple[MetrologyToolId, ...]]:
    registered = {
        MetrologyToolId(str(record.tool.tool_id))
        for record in reference.tools
        if record.tool.is_metrology
    }
    pools: dict[str, tuple[MetrologyToolId, ...]] = {}
    for method, pool in config.metrology_pools.items():
        unknown = sorted(str(gauge) for gauge in pool if gauge not in registered)
        if unknown:
            raise SimulationConfigError(
                "metrology pool names gauges that are not registered metrology tools",
                method=method,
                unknown=unknown,
            )
        pools[method] = tuple(pool)
    return pools


def _resolve_characteristic(
    row: ControlPlanCharacteristic,
    config: GeneratorConfig,
    parameters: Mapping[ParameterId, Parameter],
) -> Characteristic:
    """Turn one control-plan row into a generation-ready characteristic."""
    parameter_id = row.parameter_id
    parameter = parameters.get(parameter_id)
    if parameter is None:
        raise SimulationConfigError(
            "control plan charts a parameter that is not in the registry",
            parameter_id=str(parameter_id),
        )

    interval = FREQUENCY_INTERVALS.get(row.frequency)
    if interval is None:
        raise SimulationConfigError(
            "control plan uses an unrecognised sampling frequency",
            parameter_id=str(parameter_id),
            frequency=row.frequency,
            supported=sorted(FREQUENCY_INTERVALS),
        )

    sample_size = row.sample_size
    if sample_size > config.schedule.wafers_per_lot:
        raise SimulationConfigError(
            "control plan measures more wafers than the lot carries",
            parameter_id=str(parameter_id),
            sample_size=sample_size,
            wafers_per_lot=config.schedule.wafers_per_lot,
        )

    if parameter.sampling_sites not in SUPPORTED_SITE_COUNTS:
        raise SimulationConfigError(
            "parameter declares a sampling plan the generator cannot lay out",
            parameter_id=str(parameter_id),
            sampling_sites=parameter.sampling_sites,
            supported=list(SUPPORTED_SITE_COUNTS),
        )

    # Fails here rather than mid-generation if the parameter has no physics.
    config.physics_for(parameter_id)

    return Characteristic(
        parameter=parameter,
        product_id=row.product_id,
        step_id=row.step_id,
        chart_type=row.chart_type,
        sample_size=sample_size,
        lot_interval=interval,
    )


def build_topology(reference: ReferenceData, config: GeneratorConfig) -> Topology:
    """Resolve reference data and generator configuration into one fab model.

    Every inconsistency between the two is a failure here, before a single
    measurement exists. The alternative — discovering mid-run that a step has no
    tool or a characteristic has no specification — produces a partial dataset
    whose manifest is already wrong.

    Parameters
    ----------
    reference
        The committed reference set loaded from ``data/reference/``.
    config
        The generator configuration for this dataset.

    Raises
    ------
    SimulationConfigError
        On any disagreement between the two, naming the entity at fault.
    """
    parameters = {parameter.parameter_id: parameter for parameter in reference.parameters}
    tools_by_step, chambers_by_tool = _build_equipment(reference)
    gauges_by_method = _validate_gauge_pools(reference, config)

    specifications: dict[SpecificationKey, list[SpecificationLimit]] = {}
    for limit in reference.specification_limits:
        key = (limit.parameter_id, limit.product_id, limit.step_id)
        specifications.setdefault(key, []).append(limit)

    wanted_products = {entry.product_id for entry in config.product_mix}
    by_product: dict[ProductId, list[Characteristic]] = {product: [] for product in wanted_products}

    for plan in reference.control_plans:
        for row in plan.characteristics:
            if row.product_id not in wanted_products:
                continue
            resolved = _resolve_characteristic(row, config, parameters)
            _require_equipment(resolved, tools_by_step, chambers_by_tool)
            _require_specification(resolved, specifications, at=config.schedule.start_at)
            _require_gauge_pool(resolved, gauges_by_method)
            by_product[resolved.product_id].append(resolved)

    empty = sorted(str(product) for product, rows in by_product.items() if not rows)
    if empty:
        raise SimulationConfigError(
            "product is in the mix but no control plan charts anything for it",
            products=empty,
        )

    return Topology(
        tools_by_step=tools_by_step,
        chambers_by_tool=chambers_by_tool,
        gauges_by_method=gauges_by_method,
        characteristics_by_product={
            product: tuple(rows) for product, rows in sorted(by_product.items())
        },
        specifications={key: tuple(limits) for key, limits in specifications.items()},
        step_positions={
            step.step_id: position for position, step in enumerate(reference.process_steps)
        },
    )


def _require_equipment(
    characteristic: Characteristic,
    tools_by_step: Mapping[StepId, Sequence[ToolId]],
    chambers_by_tool: Mapping[ToolId, Sequence[ChamberId]],
) -> None:
    tools = tools_by_step.get(characteristic.step_id, ())
    if not tools:
        raise SimulationConfigError(
            "charted step has no process tool",
            step_id=str(characteristic.step_id),
            parameter_id=str(characteristic.parameter_id),
        )
    without_chambers = sorted(str(tool) for tool in tools if not chambers_by_tool.get(tool))
    if without_chambers:
        raise SimulationConfigError(
            "process tool has no chambers, so a measurement could not name one",
            step_id=str(characteristic.step_id),
            tools=without_chambers,
        )


def _require_specification(
    characteristic: Characteristic,
    specifications: Mapping[SpecificationKey, Sequence[SpecificationLimit]],
    *,
    at: datetime,
) -> None:
    key = (characteristic.parameter_id, characteristic.product_id, characteristic.step_id)
    in_force = [limit for limit in specifications.get(key, ()) if _in_force(limit, at)]
    if not in_force:
        raise SimulationConfigError(
            "charted characteristic has no specification limit in force at the dataset start",
            parameter_id=str(characteristic.parameter_id),
            product_id=str(characteristic.product_id),
            step_id=str(characteristic.step_id),
            at=at.isoformat(),
        )


def _require_gauge_pool(
    characteristic: Characteristic,
    gauges_by_method: Mapping[str, Sequence[MetrologyToolId]],
) -> None:
    method = characteristic.parameter.metrology_method
    if not gauges_by_method.get(method):
        raise SimulationConfigError(
            "no gauge pool declared for the metrology method this parameter uses",
            parameter_id=str(characteristic.parameter_id),
            method=method,
        )
