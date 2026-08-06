"""Generator configuration validation.

Every rule here exists to turn a configuration mistake into a loud failure at
load time rather than a plausible-looking dataset that nobody intended.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from spc_platform.common.errors import NaiveDatetimeError, SimulationConfigError
from spc_platform.domain.ids import ParameterId, ProductId
from spc_platform.simulation.models import (
    FaultKind,
    FaultSpec,
    GeneratorConfig,
    ParameterPhysics,
    RandomWeights,
    ScheduleConfig,
    SystematicFractions,
    ValueDistribution,
    VarianceProfile,
    load_generator_config,
)

PROFILE = VarianceProfile(
    random_weights=RandomWeights(lot=1.0, wafer=1.0, site_residual=1.0, gauge=0.5),
    systematic=SystematicFractions(tool_offset=0.4, chamber_offset=0.3, slot=0.2, spatial=0.5),
)

SCHEDULE = ScheduleConfig(
    start_at=datetime(2025, 1, 1, tzinfo=UTC),
    lots=10,
    wafers_per_lot=25,
    lot_interval_minutes=60,
    step_interval_minutes=10,
    wafer_interval_seconds=30,
)


def a_config(**overrides: object) -> GeneratorConfig:
    """Build a minimal valid configuration, with overrides applied."""
    fields: dict[str, Any] = {
        "dataset_id": "test",
        "seed": 1,
        "schedule": SCHEDULE,
        "product_mix": [{"product_id": "DEV-A", "weight": 1.0}],
        "metrology_pools": {"cd-sem": ["MET-CDSEM-01"]},
        "default_variance": PROFILE,
        "parameters": [{"parameter_id": "POLY_CD", "target_cp": 1.2}],
    }
    fields.update(overrides)
    return GeneratorConfig.model_validate(fields)


class TestParameterPhysics:
    """One parameter's declared behaviour."""

    def test_declaring_both_scales_is_refused(self) -> None:
        """Two answers to 'how wide is this parameter' is one too many."""
        with pytest.raises(ValidationError, match="exactly one of target_cp or sigma_total"):
            ParameterPhysics(parameter_id=ParameterId("P"), target_cp=1.2, sigma_total=2.0)

    def test_declaring_neither_scale_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exactly one of target_cp or sigma_total"):
            ParameterPhysics(parameter_id=ParameterId("P"))

    def test_an_unknown_key_is_refused(self) -> None:
        """A misspelled key that was ignored would produce unintended data."""
        with pytest.raises(ValidationError):
            ParameterPhysics.model_validate(
                {"parameter_id": "P", "target_cp": 1.2, "spatial_signatures": "radial"}
            )

    def test_a_normal_distribution_is_the_default(self) -> None:
        parameter = ParameterPhysics(parameter_id=ParameterId("P"), target_cp=1.2)

        assert parameter.distribution is ValueDistribution.NORMAL


class TestFaultSpec:
    """Each fault kind carries the fields its behaviour needs."""

    @pytest.mark.parametrize(
        ("kind", "extra", "missing"),
        [
            (FaultKind.VARIANCE_INCREASE, {}, "variance_factor"),
            (FaultKind.CYCLIC, {"magnitude_sigma": 1.0}, "period_lots"),
            (FaultKind.OUTLIER, {"magnitude_sigma": 1.0}, "rate"),
            (FaultKind.SPATIAL_CHANGE, {}, "signature"),
            (FaultKind.TOOL_EXCURSION, {"magnitude_sigma": 1.0}, "tool_id"),
        ],
    )
    def test_a_kind_without_its_required_field_is_refused(
        self,
        kind: FaultKind,
        extra: dict[str, Any],
        missing: str,
    ) -> None:
        with pytest.raises(ValidationError, match=missing):
            FaultSpec.model_validate(
                {
                    "fault_id": "F",
                    "kind": kind,
                    "parameter_id": "P",
                    "onset_fraction": 0.5,
                    **extra,
                }
            )

    def test_metrology_drift_needs_a_gauge_rather_than_a_parameter(self) -> None:
        """It reaches every parameter that gauge measures; naming one would be wrong."""
        with pytest.raises(ValidationError, match="metrology_tool_id"):
            FaultSpec.model_validate(
                {
                    "fault_id": "F",
                    "kind": FaultKind.METROLOGY_DRIFT,
                    "onset_fraction": 0.5,
                    "magnitude_sigma": 1.0,
                }
            )

    def test_a_process_fault_without_a_parameter_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="requires parameter_id"):
            FaultSpec.model_validate(
                {
                    "fault_id": "F",
                    "kind": FaultKind.STEP_SHIFT,
                    "onset_fraction": 0.5,
                    "magnitude_sigma": 1.0,
                }
            )

    def test_a_zero_magnitude_shift_is_refused(self) -> None:
        """A fault of size zero is not ground truth; it is a fault that is absent."""
        with pytest.raises(ValidationError, match="non-zero magnitude_sigma"):
            FaultSpec.model_validate(
                {
                    "fault_id": "F",
                    "kind": FaultKind.STEP_SHIFT,
                    "parameter_id": "P",
                    "onset_fraction": 0.5,
                }
            )

    def test_an_onset_at_the_end_of_the_run_is_refused(self) -> None:
        """A fault whose onset falls past the last lot is refused.

        A fault that starts after the last lot appears in the manifest and in
        no measurement, which is a ground truth the data cannot support.
        """
        with pytest.raises(ValidationError):
            FaultSpec.model_validate(
                {
                    "fault_id": "F",
                    "kind": FaultKind.STEP_SHIFT,
                    "parameter_id": "P",
                    "onset_fraction": 1.0,
                    "magnitude_sigma": 1.0,
                }
            )


class TestGeneratorConfig:
    """The whole configuration."""

    @pytest.mark.parametrize("dataset_id", ["", "Has Spaces", "../escape", "UPPER", "a" * 65])
    def test_an_unsafe_dataset_id_is_refused(self, dataset_id: str) -> None:
        """The id names an output directory, so it must not be able to traverse one."""
        with pytest.raises(ValidationError, match="dataset_id"):
            a_config(dataset_id=dataset_id)

    def test_duplicate_parameters_are_refused(self) -> None:
        """Two physics for one parameter means the later one silently wins."""
        with pytest.raises(ValidationError, match="duplicate parameter"):
            a_config(
                parameters=[
                    {"parameter_id": "POLY_CD", "target_cp": 1.2},
                    {"parameter_id": "POLY_CD", "target_cp": 1.4},
                ]
            )

    def test_duplicate_fault_ids_are_refused(self) -> None:
        """Fault ids key the ground truth; two rows under one key is not truth."""
        fault = {
            "kind": FaultKind.STEP_SHIFT,
            "parameter_id": "POLY_CD",
            "onset_fraction": 0.5,
            "magnitude_sigma": 1.0,
        }
        with pytest.raises(ValidationError, match="duplicate fault"):
            a_config(faults=[{"fault_id": "F", **fault}, {"fault_id": "F", **fault}])

    def test_duplicate_products_are_refused(self) -> None:
        with pytest.raises(ValidationError, match="duplicate product"):
            a_config(
                product_mix=[
                    {"product_id": "DEV-A", "weight": 0.5},
                    {"product_id": "DEV-A", "weight": 0.5},
                ]
            )

    def test_an_empty_metrology_pool_is_refused(self) -> None:
        """A method with no gauge cannot measure anything that needs it."""
        with pytest.raises(ValidationError, match="metrology pool"):
            a_config(metrology_pools={"cd-sem": []})

    def test_a_naive_start_instant_is_refused(self) -> None:
        """A start instant without a timezone is refused.

        Raised as the typed platform error rather than folded into a pydantic
        one, so a caller can distinguish 'no timezone' from 'malformed config'.
        """
        with pytest.raises(NaiveDatetimeError, match=r"schedule\.start_at"):
            a_config(
                schedule=SCHEDULE.model_copy(update={"start_at": datetime(2025, 1, 1)})  # noqa: DTZ001
            )

    def test_physics_are_looked_up_by_parameter(self) -> None:
        config = a_config()

        assert config.physics_for(ParameterId("POLY_CD")).target_cp == 1.2

    def test_a_charted_parameter_with_no_physics_is_an_error(self) -> None:
        """Falling back to a default would invent behaviour nobody described."""
        with pytest.raises(SimulationConfigError, match="no physics for"):
            a_config().physics_for(ParameterId("NOT_CONFIGURED"))

    def test_a_parameter_without_its_own_profile_uses_the_default(self) -> None:
        config = a_config()
        physics = config.physics_for(ParameterId("POLY_CD"))

        assert config.variance_for(physics) is config.default_variance

    def test_the_revision_changes_with_the_configuration(self) -> None:
        """Changing the configuration changes its revision.

        A manifest that recorded the same revision for two configurations would
        make two different datasets indistinguishable in an audit.
        """
        assert a_config().revision() != a_config(seed=2).revision()

    def test_the_revision_is_stable_across_equal_configurations(self) -> None:
        assert a_config().revision() == a_config().revision()


class TestLoading:
    """Reading a configuration from disk."""

    def test_the_committed_default_configuration_loads(self) -> None:
        config = load_generator_config(Path("configs/simulation/default.yaml"))

        assert config.dataset_id == "fab-12m"
        assert config.faults, "the default dataset exists to carry ground truth"

    def test_the_default_configuration_injects_every_fault_kind(self) -> None:
        """The fault library is the benchmark's coverage.

        A kind absent from the dataset is a kind the platform is never scored on.
        """
        config = load_generator_config(Path("configs/simulation/default.yaml"))

        assert {fault.kind for fault in config.faults} == set(FaultKind)

    def test_a_missing_file_is_reported_as_a_configuration_error(self) -> None:
        with pytest.raises(SimulationConfigError, match="not found"):
            load_generator_config(Path("configs/simulation/does-not-exist.yaml"))

    def test_invalid_yaml_is_reported_as_a_configuration_error(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.yaml"
        path.write_text("dataset_id: [unclosed\n", encoding="utf-8")

        with pytest.raises(SimulationConfigError, match="not valid YAML"):
            load_generator_config(path)

    def test_a_non_mapping_document_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "list.yaml"
        path.write_text("- one\n- two\n", encoding="utf-8")

        with pytest.raises(SimulationConfigError, match="mapping at the root"):
            load_generator_config(path)

    def test_an_unknown_top_level_key_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "extra.yaml"
        path.write_text("dataset_id: x\nunknown_key: 1\n", encoding="utf-8")

        with pytest.raises(SimulationConfigError, match="failed validation"):
            load_generator_config(path)


def test_product_ids_round_trip_as_declared() -> None:
    config = a_config(product_mix=[{"product_id": "DEV-B", "weight": 1.0}])

    assert config.product_mix[0].product_id == ProductId("DEV-B")
