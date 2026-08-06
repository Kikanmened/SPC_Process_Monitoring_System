"""The ground-truth manifest: what it records, and how it survives a round trip."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from tests.fixtures.simulation import build, short_config

from spc_platform.common.errors import GroundTruthError
from spc_platform.domain.ids import ConfigRevision, ParameterId, ProductId
from spc_platform.simulation.manifests import (
    DatasetManifest,
    dataset_revision_for,
    read_manifest,
    scale_key,
)


@pytest.fixture(scope="module")
def manifest() -> DatasetManifest:
    return build(short_config(lots=12)).manifest


def test_the_manifest_embeds_the_configuration_rather_than_pointing_at_it(
    manifest: DatasetManifest,
) -> None:
    """A manifest naming a config file records only where the truth used to be.

    An edited file leaves the dataset undescribed.
    """
    assert manifest.config.seed == manifest.seed
    assert manifest.config.parameters


def test_the_manifest_records_every_revision_needed_to_reproduce(
    manifest: DatasetManifest,
) -> None:
    assert manifest.seed >= 0
    assert manifest.code_revision
    assert manifest.config_revision
    assert manifest.generator_version


def test_a_fault_is_retrievable_by_identifier(manifest: DatasetManifest) -> None:
    first = manifest.faults[0]

    assert manifest.fault(first.fault_id) is first


def test_asking_for_an_uninjected_fault_is_an_error(manifest: DatasetManifest) -> None:
    """Asking the manifest for a fault it never recorded raises.

    Scoring against a fault the dataset does not contain is a defect in the
    test, not a missed detection, and must not read as one.
    """
    with pytest.raises(GroundTruthError, match="no such fault"):
        manifest.fault("F99-NOT-INJECTED")


def test_every_fault_carries_an_onset_the_data_can_be_searched_at(
    manifest: DatasetManifest,
) -> None:
    for fault in manifest.faults:
        assert fault.onset_lot_index >= 0
        assert fault.onset_at.tzinfo is not None


def test_a_single_parameter_fault_records_its_magnitude_in_the_parameter_unit(
    manifest: DatasetManifest,
) -> None:
    """A fault scoped to one parameter and product carries an absolute magnitude.

    Sigma differs by product, so an absolute magnitude is only meaningful when
    the fault names exactly one parameter and one product.
    """
    scoped = [
        fault
        for fault in manifest.faults
        if fault.parameter_id is not None and fault.product_id is not None
    ]
    assert scoped, "the committed configuration injects parameter-scoped faults"

    for fault in scoped:
        assert fault.magnitude_absolute is not None
        assert fault.unit is not None


def test_component_scales_are_recorded_for_every_charted_characteristic(
    manifest: DatasetManifest,
) -> None:
    """These are what a variance-recovery check is scored against."""
    assert manifest.component_scales
    for scales in manifest.component_scales.values():
        assert scales["sigma_total"] > 0.0


class TestSerialisation:
    """Writing and reading a manifest."""

    def test_the_manifest_round_trips_through_json(
        self,
        manifest: DatasetManifest,
        tmp_path: Path,
    ) -> None:
        path = tmp_path / "manifest.json"
        path.write_text(manifest.to_json(), encoding="utf-8")

        assert read_manifest(path) == manifest

    def test_the_rendered_json_is_stable(self, manifest: DatasetManifest) -> None:
        """The same manifest renders to the same JSON every time.

        Keys are sorted, so a manifest diff shows what changed rather than
        what pydantic happened to order differently.
        """
        assert manifest.to_json() == manifest.to_json()

        payload = json.loads(manifest.to_json())
        assert list(payload) == sorted(payload)

    def test_a_missing_manifest_is_reported_as_a_ground_truth_error(
        self,
        tmp_path: Path,
    ) -> None:
        with pytest.raises(GroundTruthError, match="not found"):
            read_manifest(tmp_path / "absent.json")

    def test_malformed_json_is_reported_as_a_ground_truth_error(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text("{not json", encoding="utf-8")

        with pytest.raises(GroundTruthError, match="not valid JSON"):
            read_manifest(path)

    def test_a_json_document_that_is_not_a_manifest_is_refused(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        path.write_text('{"dataset_id": "x"}', encoding="utf-8")

        with pytest.raises(GroundTruthError, match="failed validation"):
            read_manifest(path)


def test_a_scale_key_names_a_parameter_on_a_product() -> None:
    assert scale_key(ParameterId("POLY_CD"), ProductId("DEV-A")) == "POLY_CD|DEV-A"


def test_the_dataset_revision_distinguishes_seeds() -> None:
    """The dataset revision separates two runs of one configuration.

    Two datasets from one configuration under different seeds are different
    datasets, and an audit trail has to be able to tell them apart.
    """
    revision = ConfigRevision("a" * 64)

    assert dataset_revision_for("fab", revision, 1) != dataset_revision_for("fab", revision, 2)


def test_the_dataset_revision_distinguishes_configurations() -> None:
    left = dataset_revision_for("fab", ConfigRevision("a" * 64), 1)
    right = dataset_revision_for("fab", ConfigRevision("b" * 64), 1)

    assert left != right


def test_generated_at_is_timezone_aware(manifest: DatasetManifest) -> None:
    assert manifest.generated_at.tzinfo is not None
    assert manifest.generated_at.astimezone(UTC) <= datetime.now(UTC)
