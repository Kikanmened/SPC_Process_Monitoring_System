"""Synthetic fab data generator — the measurement instrument for the platform.

This package is an **instrument, not a dependency**. Nothing in the platform
imports it, and it imports nothing from ``analytics/``; both directions are
enforced by ``import-linter`` contracts rather than by convention
(docs/DECISION_LOG.md ADR-0021).

The second constraint is the one that matters. A generator that composed its
data using the estimators under test would produce a benchmark that confirms
itself: the same error in both would cancel, every score would look excellent,
and the project's central claim — that its detection performance is *measured*
rather than asserted — would rest on nothing.

Usage is two calls. Reference data and configuration in, dataset and ground
truth out:

.. code-block:: python

    config = load_generator_config(Path("configs/simulation/default.yaml"))
    dataset = generate_dataset(
        config,
        load_reference_data(),
        code_revision=CodeRevision("abc1234"),
        clock=SystemClock(),
    )
    paths, manifest = write_dataset(dataset, Path("data/synthetic"))

See [DATASET_GUIDE.md](../../../docs/DATASET_GUIDE.md) §4 for the variance
structure and the fault library, and ``scripts/simulation/`` for the operator
entry points.
"""

from spc_platform.simulation.exporters import (
    DatasetFormat,
    DatasetPaths,
    content_digest,
    read_measurements,
    write_dataset,
)
from spc_platform.simulation.faults import FaultEffect, FaultScope, ResolvedFault
from spc_platform.simulation.generator import (
    RAW_COLUMNS,
    GeneratedDataset,
    LotPlan,
    generate_dataset,
)
from spc_platform.simulation.manifests import (
    GENERATOR_VERSION,
    MANIFEST_FILENAME,
    DatasetManifest,
    FaultRecord,
    MessinessRecord,
    read_manifest,
)
from spc_platform.simulation.models import (
    FaultKind,
    FaultSpec,
    GeneratorConfig,
    MessinessConfig,
    ParameterPhysics,
    RandomWeights,
    ScheduleConfig,
    SystematicFractions,
    ValueDistribution,
    VarianceProfile,
    load_generator_config,
)
from spc_platform.simulation.spatial import (
    SUPPORTED_SITE_COUNTS,
    WAFER_RADIUS_MM,
    sampling_plan,
    signature_profile,
)
from spc_platform.simulation.topology import Characteristic, Topology, build_topology
from spc_platform.simulation.validators import Check, ValidationReport, validate_dataset
from spc_platform.simulation.variance import ComponentScales, resolve_scales

__all__ = [
    "GENERATOR_VERSION",
    "MANIFEST_FILENAME",
    "RAW_COLUMNS",
    "SUPPORTED_SITE_COUNTS",
    "WAFER_RADIUS_MM",
    "Characteristic",
    "Check",
    "ComponentScales",
    "DatasetFormat",
    "DatasetManifest",
    "DatasetPaths",
    "FaultEffect",
    "FaultKind",
    "FaultRecord",
    "FaultScope",
    "FaultSpec",
    "GeneratedDataset",
    "GeneratorConfig",
    "LotPlan",
    "MessinessConfig",
    "MessinessRecord",
    "ParameterPhysics",
    "RandomWeights",
    "ResolvedFault",
    "ScheduleConfig",
    "SystematicFractions",
    "Topology",
    "ValidationReport",
    "ValueDistribution",
    "VarianceProfile",
    "build_topology",
    "content_digest",
    "generate_dataset",
    "load_generator_config",
    "read_manifest",
    "read_measurements",
    "resolve_scales",
    "sampling_plan",
    "signature_profile",
    "validate_dataset",
    "write_dataset",
]
