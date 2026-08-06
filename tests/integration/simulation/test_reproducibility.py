"""The dataset can be rebuilt, exactly, from what the manifest records.

The generator's other claims are statistical and hold on average. This one is
exact, and everything else leans on it. A finding raised against a dataset that
cannot be rebuilt is a finding nobody can re-examine: the audit trail records a
seed and a revision (FR-RP02), and if replaying them yields different numbers
then the record names a dataset that no longer exists.

The checks run against files rather than in-memory frames deliberately. A
generator can be perfectly deterministic and still lose the property at the
storage boundary — a float that does not survive CSV, a category that comes
back as an object — and that boundary is where downstream actually reads.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from tests.fixtures.simulation import build, reference_data, short_config

from spc_platform.simulation import (
    MANIFEST_FILENAME,
    DatasetFormat,
    GeneratorConfig,
    content_digest,
    read_manifest,
    read_measurements,
    validate_dataset,
    write_dataset,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

REPRODUCTION_LOTS = 40
"""Short. These checks are about exactness, which does not need a long run."""


@pytest.fixture(scope="module")
def config() -> GeneratorConfig:
    """Return the committed configuration over a short schedule."""
    return short_config(lots=REPRODUCTION_LOTS)


class TestRegeneration:
    """Same configuration, same seed, same dataset."""

    def test_two_runs_of_the_same_configuration_agree_exactly(
        self, config: GeneratorConfig
    ) -> None:
        """Not merely statistically.

        A seed that only reproduced the distribution would let two audits of one dataset reach
        different conclusions and both be defensible.
        """
        first = build(config)
        second = build(config)

        assert content_digest(first.frame) == content_digest(second.frame)
        assert first.manifest.model_dump(mode="json") == second.manifest.model_dump(mode="json")

    def test_a_different_seed_gives_a_different_dataset(self, config: GeneratorConfig) -> None:
        """The counterpart.

        If the seed did not reach the values, the agreement above would be telling us nothing about
        determinism.
        """
        other = build(short_config(lots=REPRODUCTION_LOTS, seed=config.seed + 1))
        baseline = build(config)

        assert content_digest(other.frame) != content_digest(baseline.frame)

    def test_a_reseed_runs_the_same_fab(self, config: GeneratorConfig) -> None:
        """A new seed is a new set of wafers through the same fab, not a new fab.

        Which equipment a lot happens to land on is exactly what the seed is allowed to change, so
        the property is containment: every tool, chamber, and step in the dataset must be one the
        reference data registers.
        """
        other = build(short_config(lots=REPRODUCTION_LOTS, seed=config.seed + 1))
        reference = reference_data()

        registered = {
            "tool_id": {str(record.tool.tool_id) for record in reference.tools},
            "chamber_id": {
                str(chamber.chamber_id) for record in reference.tools for chamber in record.chambers
            },
            "step_id": {str(step.step_id) for step in reference.process_steps},
            "parameter_id": {str(parameter.parameter_id) for parameter in reference.parameters},
        }
        for column, allowed in registered.items():
            assert set(other.frame[column]) <= allowed, column


@pytest.mark.parametrize("dataset_format", list(DatasetFormat))
class TestStorageRoundTrip:
    """What is read back is what was written."""

    def test_the_written_dataset_reads_back_identically(
        self,
        config: GeneratorConfig,
        tmp_path: Path,
        dataset_format: DatasetFormat,
    ) -> None:
        """What is read back carries the digest the manifest recorded.

        Digested from the frame rather than from the file, so the check holds
        across formats and compression codecs and fails only when a value
        changed.
        """
        dataset = build(config)
        paths, manifest = write_dataset(dataset, tmp_path, dataset_format=dataset_format)

        restored = read_measurements(paths.measurements)

        assert content_digest(restored) == manifest.content_digest
        assert content_digest(dataset.frame) == manifest.content_digest

    def test_the_manifest_survives_the_journey_to_disk(
        self,
        config: GeneratorConfig,
        tmp_path: Path,
        dataset_format: DatasetFormat,
    ) -> None:
        """The manifest survives the journey to disk unchanged.

        Including the configuration embedded in it, which is what a later run
        would be replayed from.
        """
        dataset = build(config)
        paths, manifest = write_dataset(dataset, tmp_path, dataset_format=dataset_format)

        restored = read_manifest(paths.directory / MANIFEST_FILENAME)

        assert restored.model_dump(mode="json") == manifest.model_dump(mode="json")
        assert restored.config.seed == config.seed
        assert restored.config.revision() == config.revision()

    def test_a_dataset_read_from_disk_still_passes_its_own_checks(
        self,
        config: GeneratorConfig,
        tmp_path: Path,
        dataset_format: DatasetFormat,
    ) -> None:
        """A dataset read from disk still passes its own statistical checks.

        The end-to-end statement: a consumer who has only the files can confirm
        the ground truth without rerunning the generator.
        """
        paths, manifest = write_dataset(build(config), tmp_path, dataset_format=dataset_format)

        report = validate_dataset(read_measurements(paths.measurements), manifest)

        assert report.passed, report.summary()
