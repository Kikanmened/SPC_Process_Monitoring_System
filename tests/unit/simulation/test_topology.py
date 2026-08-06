"""Resolving reference data and generator configuration into one fab model.

Every check here fails before a measurement exists. The alternative — finding
mid-run that a step has no tool — produces a partial dataset whose manifest is
already wrong.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from tests.fixtures.simulation import default_config

from spc_platform.common.errors import SimulationConfigError
from spc_platform.config import load_reference_data
from spc_platform.config.reference import ReferenceData
from spc_platform.domain.ids import MetrologyToolId, ParameterId, ProductId, StepId
from spc_platform.simulation.models import GeneratorConfig, ProductMixEntry
from spc_platform.simulation.topology import (
    FREQUENCY_INTERVALS,
    Topology,
    build_topology,
    recipe_for,
)


@pytest.fixture(scope="module")
def reference() -> ReferenceData:
    return load_reference_data()


@pytest.fixture(scope="module")
def config() -> GeneratorConfig:
    return default_config()


@pytest.fixture(scope="module")
def topology(reference: ReferenceData, config: GeneratorConfig) -> Topology:
    return build_topology(reference, config)


def test_the_committed_fab_model_resolves(topology: Topology) -> None:
    assert topology.characteristics_by_product
    assert topology.tools_by_step
    assert topology.step_positions


def test_every_product_in_the_mix_charts_something(
    topology: Topology,
    config: GeneratorConfig,
) -> None:
    charted = set(topology.characteristics_by_product)

    assert charted == {entry.product_id for entry in config.product_mix}


def test_every_charted_step_has_at_least_two_tools(topology: Topology) -> None:
    """Commonality analysis needs something to compare against.

    A single-tool step makes tool-to-tool mismatch undetectable in principle.
    """
    charted_steps = {
        characteristic.step_id
        for characteristics in topology.characteristics_by_product.values()
        for characteristic in characteristics
    }

    single = sorted(
        str(step) for step in charted_steps if len(topology.tools_by_step.get(step, ())) < 2
    )
    assert not single, f"steps with fewer than two tools: {single}"


def test_every_process_tool_has_chambers(topology: Topology) -> None:
    """A measurement has to name a chamber, so a tool without one cannot run."""
    bare = sorted(str(tool) for tool, chambers in topology.chambers_by_tool.items() if not chambers)

    assert not bare


def test_step_positions_order_the_route(topology: Topology, reference: ReferenceData) -> None:
    positions = [topology.step_positions[step.step_id] for step in reference.process_steps]

    assert positions == sorted(positions)


def test_a_characteristic_is_due_on_the_lots_its_frequency_names(topology: Topology) -> None:
    characteristics = next(iter(topology.characteristics_by_product.values()))
    every_lot = next(c for c in characteristics if c.lot_interval == 1)

    assert all(every_lot.is_due(index) for index in range(5))


def test_a_five_lot_characteristic_skips_four_lots_in_five(topology: Topology) -> None:
    characteristics = [
        characteristic
        for characteristics in topology.characteristics_by_product.values()
        for characteristic in characteristics
        if characteristic.lot_interval == FREQUENCY_INTERVALS["every_5th_lot"]
    ]
    if not characteristics:
        pytest.skip("no characteristic in the committed plan is sampled every fifth lot")

    due = [index for index in range(20) if characteristics[0].is_due(index)]
    assert due == [0, 5, 10, 15]


def test_a_recipe_names_its_step_and_product() -> None:
    recipe = recipe_for(StepId("POLY_ETCH"), ProductId("DEV-A"))

    assert str(recipe) == "RCP-POLY_ETCH-DEV-A"


class TestSpecificationLookup:
    """Resolving which limit was in force at an instant."""

    def test_the_limit_in_force_at_the_dataset_start_is_returned(
        self,
        topology: Topology,
        config: GeneratorConfig,
    ) -> None:
        characteristic = topology.characteristics_by_product[ProductId("DEV-A")][0]
        key = (characteristic.parameter_id, ProductId("DEV-A"), characteristic.step_id)

        limit = topology.specification_at(key, config.schedule.start_at)

        assert limit.parameter_id == characteristic.parameter_id

    def test_an_instant_before_every_effective_date_has_no_limit(
        self,
        topology: Topology,
    ) -> None:
        """Before every effective date, no limit is in force.

        The reference data cannot answer 'what was the limit', and guessing
        would put a target in the manifest that no document supports.
        """
        characteristic = topology.characteristics_by_product[ProductId("DEV-A")][0]
        key = (characteristic.parameter_id, ProductId("DEV-A"), characteristic.step_id)

        with pytest.raises(SimulationConfigError, match="no specification limit in force"):
            topology.specification_at(key, datetime(1990, 1, 1, tzinfo=UTC))

    def test_a_retired_limit_stops_applying_at_its_end_date(
        self,
        topology: Topology,
    ) -> None:
        """A limit stops applying on its end date.

        The committed data retains a superseded POLY_CD limit for DEV-A, which
        is what lets a capability change be told apart from a process change.
        """
        key = (ParameterId("POLY_CD"), ProductId("DEV-A"), StepId("POLY_ETCH"))
        history = topology.specifications[key]
        if len(history) < 2:
            pytest.skip("no specification history committed for POLY_CD on DEV-A")

        retired = min(history, key=lambda limit: limit.effective_from)
        assert retired.effective_to is not None

        before = topology.specification_at(key, retired.effective_to - timedelta(days=1))
        after = topology.specification_at(key, retired.effective_to)
        assert before is retired
        assert after is not retired


class TestConsistencyChecks:
    """Disagreements between reference data and configuration."""

    def test_a_gauge_that_is_not_a_registered_tool_is_refused(
        self,
        reference: ReferenceData,
        config: GeneratorConfig,
    ) -> None:
        """A gauge the reference data does not register is refused.

        Otherwise the generator emits measurements naming equipment that does
        not exist, and the pipeline rejects them as if it were at fault.
        """
        broken = config.model_copy(
            update={"metrology_pools": {"cd-sem": (MetrologyToolId("MET-NOPE-99"),)}}
        )

        with pytest.raises(SimulationConfigError, match="not registered metrology tools"):
            build_topology(reference, broken)

    def test_a_product_with_no_control_plan_is_refused(
        self,
        reference: ReferenceData,
        config: GeneratorConfig,
    ) -> None:
        """It would contribute lots and no measurements — a silent hole in the mix."""
        broken = config.model_copy(
            update={"product_mix": (ProductMixEntry(product_id=ProductId("DEV-NONE"), weight=1.0),)}
        )

        with pytest.raises(SimulationConfigError, match="no control plan charts"):
            build_topology(reference, broken)

    def test_a_lot_smaller_than_the_sample_size_is_refused(
        self,
        reference: ReferenceData,
        config: GeneratorConfig,
    ) -> None:
        broken = config.model_copy(
            update={"schedule": config.schedule.model_copy(update={"wafers_per_lot": 1})}
        )

        with pytest.raises(SimulationConfigError, match="more wafers than the lot carries"):
            build_topology(reference, broken)

    def test_a_parameter_without_physics_is_refused(
        self,
        reference: ReferenceData,
        config: GeneratorConfig,
    ) -> None:
        """Charted but undescribed: the generator would have to invent behaviour."""
        broken = config.model_copy(update={"parameters": config.parameters[:1]})

        with pytest.raises(SimulationConfigError, match="no physics for"):
            build_topology(reference, broken)
