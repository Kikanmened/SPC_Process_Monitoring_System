"""Injected faults, and the ground truth they produce (DATASET_GUIDE.md §4.3).

Every fault here has a known kind, a known scope, a known onset, and a known
magnitude. That is the whole reason the data is synthetic: a real dataset has no
ground truth, so a detection engine evaluated on it can only be inspected, and
"the charts look reasonable" is not evidence
([TESTING_STRATEGY.md](../../../docs/TESTING_STRATEGY.md) §3.5).

Magnitudes are expressed in units of the affected parameter's total random
sigma. A gauge drifting "by 1.5 sigma" therefore means 1.5 of *each* affected
parameter's sigma rather than a single absolute displacement — a simplification,
since a real gauge drifts in its own units, but the one that keeps a detection
claim of the form "≥ 95% for shifts ≥ 1.5 sigma" directly checkable against the
manifest.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from spc_platform.domain.enums import SpatialSignature
from spc_platform.domain.ids import (
    ChamberId,
    MetrologyToolId,
    ParameterId,
    ProductId,
    ToolId,
)
from spc_platform.simulation.models import FaultKind, FaultSpec, GeneratorConfig

_LEVEL_KINDS = frozenset(
    {
        FaultKind.GRADUAL_DRIFT,
        FaultKind.STEP_SHIFT,
        FaultKind.CYCLIC,
        FaultKind.TOOL_EXCURSION,
    }
)


@dataclass(frozen=True, slots=True)
class ResolvedFault:
    """A fault with its onset resolved against the actual lot schedule."""

    spec: FaultSpec
    onset_lot_index: int
    onset_at: datetime


@dataclass(frozen=True, slots=True)
class FaultScope:
    """The entities one block of measurements belongs to."""

    parameter_id: ParameterId
    product_id: ProductId
    tool_id: ToolId
    chamber_id: ChamberId
    metrology_tool_id: MetrologyToolId


@dataclass(frozen=True, slots=True)
class OutlierSpec:
    """One active outlier source: how often, and how far."""

    fault_id: str
    rate: float
    magnitude: float


@dataclass(frozen=True, slots=True)
class FaultEffect:
    """The combined effect of every applicable fault at one point in time.

    Separating the process level from the gauge level is the point of the whole
    module. A platform that adds them together cannot tell a drifting chamber
    from a drifting gauge, and will send an engineer to the wrong tool.
    """

    level_offset: float = 0.0
    gauge_offset: float = 0.0
    process_variance_multiplier: float = 1.0
    """Factor on the variance of the random *process* terms, not on their sigma.

    The gauge term is deliberately excluded: a degrading mass-flow controller
    widens the process and leaves the metrology alone, and a fault that moved
    both would be indistinguishable from a gauge problem.
    """

    spatial_override: SpatialSignature | None = None
    spatial_amplitude_multiplier: float = 1.0
    outliers: tuple[OutlierSpec, ...] = ()
    active_fault_ids: tuple[str, ...] = ()


def resolve_faults(
    config: GeneratorConfig,
    lot_starts: Sequence[datetime],
) -> tuple[ResolvedFault, ...]:
    """Place each configured fault at a concrete lot index and instant.

    ``onset_fraction`` is resolved against the actual number of lots, so a fault
    declared a third of the way through stays a third of the way through when
    the dataset is regenerated at a different length.
    """
    lot_count = len(lot_starts)
    resolved: list[ResolvedFault] = []
    for spec in config.faults:
        index = min(int(spec.onset_fraction * lot_count), lot_count - 1)
        resolved.append(ResolvedFault(spec=spec, onset_lot_index=index, onset_at=lot_starts[index]))
    return tuple(resolved)


def applies_to(fault: ResolvedFault, scope: FaultScope) -> bool:
    """Whether a fault is in scope for a block of measurements.

    Every field the fault declares must match; fields it leaves unset match
    anything. A metrology drift that names only a gauge therefore reaches every
    parameter that gauge measures, which is exactly the signature that
    distinguishes it from a process fault.
    """
    spec = fault.spec
    if spec.parameter_id is not None and spec.parameter_id != scope.parameter_id:
        return False
    if spec.product_id is not None and spec.product_id != scope.product_id:
        return False
    if spec.tool_id is not None and spec.tool_id != scope.tool_id:
        return False
    if spec.chamber_id is not None and spec.chamber_id != scope.chamber_id:
        return False
    return not (
        spec.metrology_tool_id is not None and spec.metrology_tool_id != scope.metrology_tool_id
    )


def _level_offset(fault: ResolvedFault, *, lot_index: int, lot_count: int, sigma: float) -> float:
    """Return the process-level displacement a fault imposes at ``lot_index``."""
    spec = fault.spec
    elapsed = lot_index - fault.onset_lot_index
    if elapsed < 0:
        return 0.0

    match spec.kind:
        case FaultKind.STEP_SHIFT | FaultKind.TOOL_EXCURSION:
            return spec.magnitude_sigma * sigma
        case FaultKind.GRADUAL_DRIFT:
            span = max(lot_count - 1 - fault.onset_lot_index, 1)
            return spec.magnitude_sigma * sigma * (elapsed / span)
        case FaultKind.CYCLIC:
            period = spec.period_lots or 1
            return spec.magnitude_sigma * sigma * math.sin(2.0 * math.pi * elapsed / period)
        case _:  # pragma: no cover - guarded by _LEVEL_KINDS
            return 0.0


def _gauge_offset(fault: ResolvedFault, *, lot_index: int, lot_count: int, sigma: float) -> float:
    """Return the gauge-level displacement a metrology drift imposes."""
    elapsed = lot_index - fault.onset_lot_index
    if elapsed < 0:
        return 0.0
    span = max(lot_count - 1 - fault.onset_lot_index, 1)
    return fault.spec.magnitude_sigma * sigma * (elapsed / span)


def combine(
    faults: Sequence[ResolvedFault],
    scope: FaultScope,
    *,
    lot_index: int,
    lot_count: int,
    sigma: float,
) -> FaultEffect:
    """Combine every applicable fault into one effect for a block of measurements.

    Parameters
    ----------
    faults
        All resolved faults for the dataset.
    scope
        The entities the block belongs to.
    lot_index
        Position of the lot in the schedule.
    lot_count
        Total lots, used to pace a drift across the remaining window.
    sigma
        The affected parameter's total random sigma, which is what
        ``magnitude_sigma`` is measured in.

    Returns
    -------
    FaultEffect
        Level and gauge displacements are additive across faults; a variance
        increase is multiplicative; a spatial change replaces the signature.
    """
    level = 0.0
    gauge = 0.0
    variance_multiplier = 1.0
    spatial: SpatialSignature | None = None
    spatial_multiplier = 1.0
    outliers: list[OutlierSpec] = []
    active: list[str] = []

    for fault in faults:
        if not applies_to(fault, scope):
            continue
        spec = fault.spec
        started = lot_index >= fault.onset_lot_index
        if not started:
            continue

        if spec.kind in _LEVEL_KINDS:
            level += _level_offset(fault, lot_index=lot_index, lot_count=lot_count, sigma=sigma)
        elif spec.kind is FaultKind.METROLOGY_DRIFT:
            gauge += _gauge_offset(fault, lot_index=lot_index, lot_count=lot_count, sigma=sigma)
        elif spec.kind is FaultKind.VARIANCE_INCREASE:
            variance_multiplier *= spec.variance_factor or 1.0
        elif spec.kind is FaultKind.SPATIAL_CHANGE:
            spatial = spec.signature
            if spec.magnitude_sigma:
                spatial_multiplier *= spec.magnitude_sigma
        elif spec.kind is FaultKind.OUTLIER and spec.rate is not None:
            outliers.append(
                OutlierSpec(
                    fault_id=spec.fault_id,
                    rate=spec.rate,
                    magnitude=spec.magnitude_sigma * sigma,
                )
            )
        active.append(spec.fault_id)

    return FaultEffect(
        level_offset=level,
        gauge_offset=gauge,
        process_variance_multiplier=variance_multiplier,
        spatial_override=spatial,
        spatial_amplitude_multiplier=spatial_multiplier,
        outliers=tuple(outliers),
        active_fault_ids=tuple(active),
    )
