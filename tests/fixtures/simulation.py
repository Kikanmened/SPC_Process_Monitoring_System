"""Building generated datasets for tests.

Generating the committed twelve-month dataset takes about twelve seconds, which
is too slow to sit in a test tier that runs on every commit. The reduced
schedule here keeps every product, parameter, and fault of the real
configuration and shortens only the lot count, so the tests exercise the same
code paths on the same fab model.

The floor on that lot count is statistical rather than aesthetic: the validators
need enough wafers per characteristic to estimate a variance component, and a
characteristic sampled every fifth lot only accumulates those wafers slowly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from spc_platform.common.time import Clock, FixedClock
from spc_platform.config import load_reference_data
from spc_platform.config.reference import ReferenceData
from spc_platform.domain.ids import CodeRevision
from spc_platform.simulation import (
    GeneratedDataset,
    GeneratorConfig,
    generate_dataset,
    load_generator_config,
)

DEFAULT_CONFIG_PATH = Path("configs/simulation/default.yaml")

SHORT_RUN_LOTS = 300
"""Enough lots for the validators to resolve every component they check.

The binding constraint is the per-tool bias, not the wafer count. A tool's mean
carries lot-to-lot noise, so resolving a bias of the configured size needs
roughly fifty lots on that tool — which, split across three products and a
three-tool fleet, is where this number comes from. Below it the tool-offset
check is skipped rather than passed, and the tier would stop covering the
property it exists to cover.
"""

TEST_CODE_REVISION = CodeRevision("test0000")
"""Fixed, so a manifest built in a test never depends on the working tree."""

TEST_CLOCK: Clock = FixedClock(datetime(2026, 1, 1, tzinfo=UTC))
"""Fixed, so ``generated_at`` cannot make two otherwise identical runs differ."""


def reference_data() -> ReferenceData:
    """Load the committed reference data: the fab the datasets are generated for."""
    return load_reference_data()


def default_config() -> GeneratorConfig:
    """Load the committed generator configuration, unmodified."""
    return load_generator_config(DEFAULT_CONFIG_PATH)


def short_config(*, lots: int = SHORT_RUN_LOTS, seed: int | None = None) -> GeneratorConfig:
    """Return the committed configuration with a shortened schedule.

    Parameters
    ----------
    lots
        How many lots to run. Defaults to :data:`SHORT_RUN_LOTS`.
    seed
        Overrides the configured seed, for tests that need a second independent
        realisation of the same fab.
    """
    config = default_config()
    updates: dict[str, object] = {"schedule": config.schedule.model_copy(update={"lots": lots})}
    if seed is not None:
        updates["seed"] = seed
    return config.model_copy(update=updates)


def build(config: GeneratorConfig, reference: ReferenceData | None = None) -> GeneratedDataset:
    """Generate one dataset with the fixed test revision and clock."""
    return generate_dataset(
        config,
        reference if reference is not None else reference_data(),
        code_revision=TEST_CODE_REVISION,
        clock=TEST_CLOCK,
    )
