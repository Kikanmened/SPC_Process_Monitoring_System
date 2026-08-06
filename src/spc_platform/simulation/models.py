"""Generator configuration: the hidden physics of the simulated fab.

This is deliberately *not* reference data. ``data/reference/`` holds what the
fab knows about itself — the parameters it controls, the tools it runs them on,
and the limits it holds them to. The variance structure and the injected faults
declared here are what the platform is supposed to *discover*. Keeping the two
apart is what stops the benchmark being handed its own answer.

Sampling is not configured here either. How many wafers are measured and how
often comes from the control plan in ``data/reference/control_plans.yaml``, so a
dataset cannot be sampled differently from the plan it is charted against.

A dataset is fully described by this configuration plus a seed
(DATASET_GUIDE.md §4.4).
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from spc_platform.common.errors import SimulationConfigError
from spc_platform.common.time import require_aware
from spc_platform.config.revision import compute_config_revision
from spc_platform.domain.enums import SpatialSignature
from spc_platform.domain.ids import (
    ChamberId,
    ConfigRevision,
    MetrologyToolId,
    ParameterId,
    ProductId,
    ToolId,
)

_DATASET_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_MAX_SLOTS = 25


class ValueDistribution(StrEnum):
    """How a parameter's observed value is realised from its expected level."""

    NORMAL = "normal"
    POISSON = "poisson"


class FaultKind(StrEnum):
    """The fault library (DATASET_GUIDE.md §4.3).

    ``METROLOGY_DRIFT`` is the one that is not a process fault at all. It is
    here because a platform that reports gauge drift as a process excursion
    sends engineers to the wrong tool, and separating the two is a competency
    this project intends to demonstrate rather than assert.
    """

    GRADUAL_DRIFT = "gradual_drift"
    STEP_SHIFT = "step_shift"
    VARIANCE_INCREASE = "variance_increase"
    CYCLIC = "cyclic"
    TOOL_EXCURSION = "tool_excursion"
    SPATIAL_CHANGE = "spatial_change"
    METROLOGY_DRIFT = "metrology_drift"
    OUTLIER = "outlier"


class RandomWeights(BaseModel):
    """Relative sizes of the four random variance components.

    Weights are relative, not absolute: they are rescaled so that they combine
    in quadrature to the parameter's total random sigma. Declaring them as a
    shape rather than as absolute sigmas means the same profile can be reused
    across parameters measured in nanometres and in ohms per square.

    ``gauge`` must be positive. A generator with no measurement error makes
    Gauge R&R vacuous, and %GRR is one of the numbers this data exists to let
    the platform compute.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    lot: float = Field(ge=0.0)
    wafer: float = Field(ge=0.0)
    site_residual: float = Field(ge=0.0)
    gauge: float = Field(gt=0.0)

    def normalised(self) -> tuple[float, float, float, float]:
        """Return the weights scaled so their squares sum to one.

        Returns
        -------
        tuple of float
            ``(lot, wafer, site_residual, gauge)`` as fractions of the total
            random sigma.
        """
        squares = self.lot**2 + self.wafer**2 + self.site_residual**2 + self.gauge**2
        scale = squares**0.5
        return (
            self.lot / scale,
            self.wafer / scale,
            self.site_residual / scale,
            self.gauge / scale,
        )


class SystematicFractions(BaseModel):
    """Sizes of the systematic terms, as multiples of the total random sigma.

    These sit *outside* the random total rather than inside it. Tool mismatch
    and a within-wafer signature are structure, not noise: they widen the
    overall spread without widening the short-term spread, which is precisely
    why Cp and Pp differ on real fab data and must differ here too.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_offset: float = Field(ge=0.0)
    chamber_offset: float = Field(ge=0.0)
    slot: float = Field(ge=0.0)
    spatial: float = Field(ge=0.0)


class VarianceProfile(BaseModel):
    """A complete variance shape: random components plus systematic structure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    random_weights: RandomWeights
    systematic: SystematicFractions


class ParameterPhysics(BaseModel):
    """The true behaviour of one controlled parameter.

    Exactly one of ``target_cp`` and ``sigma_total`` is given. ``target_cp``
    derives the total random sigma from the specification width, which keeps the
    fab model self-consistent: a parameter declared at Cp 1.45 should come back
    from the capability module at approximately 1.45 within a tool, and lower
    overall once tool and chamber mismatch are included. ``sigma_total`` is for
    single-sided characteristics, where there is no width to divide.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    target_cp: float | None = Field(default=None, gt=0.0)
    sigma_total: float | None = Field(default=None, gt=0.0)
    distribution: ValueDistribution = ValueDistribution.NORMAL
    spatial_signature: SpatialSignature = SpatialSignature.RADIAL
    variance: VarianceProfile | None = None

    @model_validator(mode="after")
    def _exactly_one_scale(self) -> ParameterPhysics:
        if (self.target_cp is None) == (self.sigma_total is None):
            raise ValueError(
                f"declare exactly one of target_cp or sigma_total for parameter {self.parameter_id}"
            )
        return self


class FaultSpec(BaseModel):
    """One injected fault, and therefore one row of ground truth.

    ``onset_fraction`` positions the fault in the lot sequence rather than at a
    wall-clock instant, so a fault stays where it was declared when the dataset
    is regenerated at a different length. The manifest records the resolved lot
    index and timestamp.

    ``magnitude_sigma`` is in units of the parameter's total random sigma, which
    is what makes a detection claim like "95% or better for shifts of 1.5 sigma"
    ([TESTING_STRATEGY.md](../../../docs/TESTING_STRATEGY.md) §3.5) directly
    checkable against this field.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    fault_id: str = Field(min_length=1)
    kind: FaultKind
    parameter_id: ParameterId | None = None
    product_id: ProductId | None = None
    tool_id: ToolId | None = None
    chamber_id: ChamberId | None = None
    metrology_tool_id: MetrologyToolId | None = None
    onset_fraction: float = Field(ge=0.0, lt=1.0)
    magnitude_sigma: float = 0.0
    period_lots: int | None = Field(default=None, gt=1)
    variance_factor: float | None = Field(default=None, gt=0.0)
    signature: SpatialSignature | None = None
    rate: float | None = Field(default=None, gt=0.0, le=1.0)
    note: str = ""

    @model_validator(mode="after")
    def _kind_requirements(self) -> FaultSpec:
        needs_parameter = self.kind is not FaultKind.METROLOGY_DRIFT
        if needs_parameter and self.parameter_id is None:
            raise ValueError(f"fault {self.fault_id} ({self.kind}) requires parameter_id")

        if self.kind is FaultKind.METROLOGY_DRIFT and self.metrology_tool_id is None:
            raise ValueError(f"fault {self.fault_id} requires metrology_tool_id")
        if self.kind is FaultKind.TOOL_EXCURSION and self.tool_id is None:
            raise ValueError(f"fault {self.fault_id} requires tool_id")
        if self.kind is FaultKind.VARIANCE_INCREASE and self.variance_factor is None:
            raise ValueError(f"fault {self.fault_id} requires variance_factor")
        if self.kind is FaultKind.CYCLIC and self.period_lots is None:
            raise ValueError(f"fault {self.fault_id} requires period_lots")
        if self.kind is FaultKind.OUTLIER and self.rate is None:
            raise ValueError(f"fault {self.fault_id} requires rate")
        if self.kind is FaultKind.SPATIAL_CHANGE and self.signature is None:
            raise ValueError(f"fault {self.fault_id} requires signature")

        magnitude_required = self.kind not in {
            FaultKind.VARIANCE_INCREASE,
            FaultKind.SPATIAL_CHANGE,
        }
        if magnitude_required and self.magnitude_sigma == 0.0:
            raise ValueError(f"fault {self.fault_id} requires a non-zero magnitude_sigma")
        return self


class ScheduleConfig(BaseModel):
    """When lots run, and how many wafers each carries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start_at: datetime
    lots: int = Field(gt=0)
    wafers_per_lot: int = Field(ge=1, le=_MAX_SLOTS)
    lot_interval_minutes: int = Field(gt=0)
    step_interval_minutes: int = Field(gt=0)
    wafer_interval_seconds: int = Field(gt=0)

    @model_validator(mode="after")
    def _start_is_aware(self) -> ScheduleConfig:
        require_aware(self.start_at, field_name="schedule.start_at")
        return self


class ProductMixEntry(BaseModel):
    """One device's share of the started lots."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: ProductId
    weight: float = Field(gt=0.0)


class MessinessConfig(BaseModel):
    """Rates for the data-quality situations the platform must survive.

    ``invalid_record_rate`` defaults to zero. An out-of-range value is a hard
    stop at ingest (DATASET_GUIDE.md §5), so a dataset carrying one cannot be
    loaded at all — which is exactly what the quarantine test needs and exactly
    what a demonstration dataset must not do.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    remeasurement_rate: float = Field(default=0.004, ge=0.0, le=1.0)
    missing_rate: float = Field(default=0.002, ge=0.0, le=1.0)
    invalid_record_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class GeneratorConfig(BaseModel):
    """Everything needed, with a seed, to produce one dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_id: str
    seed: int = Field(ge=0)
    description: str = ""
    schedule: ScheduleConfig
    product_mix: tuple[ProductMixEntry, ...] = Field(min_length=1)
    metrology_pools: dict[str, tuple[MetrologyToolId, ...]]
    default_variance: VarianceProfile
    parameters: tuple[ParameterPhysics, ...] = Field(min_length=1)
    faults: tuple[FaultSpec, ...] = ()
    messiness: MessinessConfig = Field(default_factory=MessinessConfig)

    @model_validator(mode="after")
    def _identifiers_are_unique_and_safe(self) -> GeneratorConfig:
        if not _DATASET_ID_PATTERN.match(self.dataset_id):
            raise ValueError(
                "dataset_id must be lowercase alphanumeric with '.', '_' or '-' "
                f"and at most 64 characters; got {self.dataset_id!r}"
            )
        _reject_duplicates(
            [str(item.parameter_id) for item in self.parameters],
            label="parameter",
        )
        _reject_duplicates([item.fault_id for item in self.faults], label="fault")
        _reject_duplicates(
            [str(item.product_id) for item in self.product_mix],
            label="product",
        )
        for method, pool in self.metrology_pools.items():
            if not pool:
                raise ValueError(f"metrology pool for {method!r} is empty")
        return self

    def physics_for(self, parameter_id: ParameterId) -> ParameterPhysics:
        """Return the declared physics for ``parameter_id``.

        Raises
        ------
        SimulationConfigError
            If the parameter is charted by a control plan but has no physics
            here. Falling back to a default would invent behaviour for a
            characteristic nobody described.
        """
        for item in self.parameters:
            if item.parameter_id == parameter_id:
                return item
        raise SimulationConfigError(
            "control plan charts a parameter the generator has no physics for",
            parameter_id=str(parameter_id),
            dataset_id=self.dataset_id,
        )

    def variance_for(self, physics: ParameterPhysics) -> VarianceProfile:
        """Return the parameter's own variance profile, or the shared default."""
        return physics.variance or self.default_variance

    def revision(self) -> ConfigRevision:
        """Return the stable digest of this configuration."""
        return compute_config_revision(self.model_dump(mode="json"))


def _reject_duplicates(values: list[str], *, label: str) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    if duplicates:
        raise ValueError(f"duplicate {label} entries: {', '.join(sorted(duplicates))}")


def load_generator_config(path: Path) -> GeneratorConfig:
    """Parse and validate a generator configuration file.

    Parameters
    ----------
    path
        Path to the YAML configuration, normally under ``configs/simulation/``.

    Raises
    ------
    SimulationConfigError
        If the file is missing, is not valid YAML, or fails validation. Unknown
        keys are a failure, not a warning: a misspelled variance component that
        was silently ignored would produce a dataset nobody intended.
    """
    if not path.is_file():
        raise SimulationConfigError("generator configuration not found", path=str(path))
    try:
        payload: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SimulationConfigError(
            "generator configuration is not valid YAML",
            path=str(path),
            reason=str(exc),
        ) from exc
    if not isinstance(payload, dict):
        raise SimulationConfigError(
            "generator configuration must contain a mapping at the root",
            path=str(path),
        )
    try:
        return GeneratorConfig.model_validate(payload)
    except ValueError as exc:
        raise SimulationConfigError(
            "generator configuration failed validation",
            path=str(path),
            reason=str(exc),
        ) from exc
