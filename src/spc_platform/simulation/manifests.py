"""The ground-truth manifest that travels with every generated dataset.

The manifest is the dataset's contract. It records what was injected, where,
and how large — the truth a detection scorecard is measured against — together
with everything needed to reproduce the data: the full configuration, the seed,
the generator version, and the code revision.

The configuration is embedded rather than referenced. A manifest pointing at a
config file records only where the truth used to be; a file that has since been
edited leaves the dataset undescribed and the scorecard unfounded.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.common.errors import GroundTruthError
from spc_platform.domain.enums import SpatialSignature
from spc_platform.domain.ids import (
    ChamberId,
    CodeRevision,
    ConfigRevision,
    MetrologyToolId,
    ParameterId,
    ProductId,
    ToolId,
    UnitSymbol,
)
from spc_platform.simulation.models import FaultKind, GeneratorConfig

GENERATOR_VERSION = "1.0.0"
"""Numerical behaviour of the generator.

Bump this whenever a change alters the values produced for an unchanged
configuration and seed. A dataset regenerated under a different version is not
required to match byte for byte, and the reproduction check says so rather than
failing with a diff nobody can interpret.
"""

MANIFEST_FILENAME = "manifest.json"
MEASUREMENTS_STEM = "measurements"


class FaultRecord(BaseModel):
    """One injected fault, as ground truth.

    ``magnitude_absolute`` is filled only when the fault names exactly one
    parameter and one product, because sigma differs by product: the 40 nm
    device carries a wider specification and therefore a larger sigma than the
    28 nm devices for the same characteristic.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fault_id: str
    kind: FaultKind
    parameter_id: ParameterId | None = None
    product_id: ProductId | None = None
    tool_id: ToolId | None = None
    chamber_id: ChamberId | None = None
    metrology_tool_id: MetrologyToolId | None = None
    onset_lot_index: int = Field(ge=0)
    onset_at: datetime
    magnitude_sigma: float
    magnitude_absolute: float | None = None
    unit: UnitSymbol | None = None
    period_lots: int | None = None
    variance_factor: float | None = None
    signature: SpatialSignature | None = None
    note: str = ""


class MessinessRecord(BaseModel):
    """Counts of the data-quality situations actually realised in this dataset.

    Rates are configured; counts are observed. Recording the counts means a test
    can assert on what the dataset contains rather than on what it was asked to
    contain.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    measurements_before_messiness: int = Field(ge=0)
    remeasurement_events: int = Field(ge=0)
    """Wafer-and-parameter pairs sent back to metrology, not distinct wafers.

    One wafer remeasured for two parameters is two events, because the fab
    performed two of them and each produced its own superseded record.
    """

    superseded_records: int = Field(ge=0)
    missing_measurements: int = Field(ge=0)
    invalid_records: int = Field(ge=0)
    outlier_points: int = Field(ge=0)


class DatasetManifest(BaseModel):
    """Everything needed to interpret, score, and reproduce one dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    generated_at: datetime
    generator_version: str
    seed: int
    code_revision: CodeRevision
    config_revision: ConfigRevision
    dataset_revision: str
    row_count: int = Field(ge=0)
    content_digest: str
    config: GeneratorConfig
    faults: tuple[FaultRecord, ...] = ()
    messiness: MessinessRecord
    component_scales: dict[str, dict[str, float]] = Field(default_factory=dict)
    tool_offsets: dict[str, dict[str, float]] = Field(default_factory=dict)
    """Each tool's fixed bias, per characteristic, in the parameter's unit.

    Ground truth for commonality analysis. Module 7 is meant to answer "which
    tool is high, and by how much"; without the individual offsets recorded, an
    answer could only be inspected, never scored. The spread of these numbers is
    ``sigma_tool_offset`` in :attr:`component_scales`, but the spread alone is
    not enough — a fleet of three tools has three biases, and a platform that
    named the wrong one would still match the spread exactly.
    """

    chamber_offsets: dict[str, dict[str, float]] = Field(default_factory=dict)
    """Each chamber's fixed bias, per characteristic, in the parameter's unit.

    Centred within its tool, so a chamber excursion is separable from the tool
    bias it sits inside.
    """

    def fault(self, fault_id: str) -> FaultRecord:
        """Return one fault record by identifier.

        Raises
        ------
        GroundTruthError
            If no such fault was injected. Scoring against a fault the dataset
            does not contain is a defect in the test, not a missed detection.
        """
        for record in self.faults:
            if record.fault_id == fault_id:
                return record
        raise GroundTruthError(
            "manifest has no such fault",
            fault_id=fault_id,
            dataset_id=self.dataset_id,
        )

    def to_json(self) -> str:
        """Render the manifest as stable, human-readable JSON."""
        payload = self.model_dump(mode="json")
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def scale_key(parameter_id: ParameterId, product_id: ProductId) -> str:
    """Return the key under which resolved sigmas are recorded."""
    return f"{parameter_id}|{product_id}"


def dataset_revision_for(dataset_id: str, config_revision: ConfigRevision, seed: int) -> str:
    """Return the generator's own identifier for a dataset.

    Distinct from the pipeline's ``data_revision``, which is assigned at ingest
    (DATASET_GUIDE.md §6). This one names what the generator produced; that one
    names what the pipeline admitted.
    """
    return f"syn-{dataset_id}-{seed}-{str(config_revision)[:12]}"


def read_manifest(path: Path) -> DatasetManifest:
    """Load and validate a manifest from disk.

    Raises
    ------
    GroundTruthError
        If the file is missing or does not parse as a manifest.
    """
    if not path.is_file():
        raise GroundTruthError("manifest not found", path=str(path))
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GroundTruthError(
            "manifest is not valid JSON",
            path=str(path),
            reason=str(exc),
        ) from exc
    try:
        return DatasetManifest.model_validate(payload)
    except ValueError as exc:
        raise GroundTruthError(
            "manifest failed validation",
            path=str(path),
            reason=str(exc),
        ) from exc
