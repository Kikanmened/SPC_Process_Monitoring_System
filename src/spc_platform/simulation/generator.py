"""Assembly of the synthetic dataset.

The composition order matters and mirrors the physical one: material arrives
with a lot-level bias, runs on a tool with a persistent offset, is distributed
across chambers that differ from one another, sits in a slot with a position
effect, acquires a within-wafer signature from the process, and is finally read
by a gauge that adds its own error. Faults displace one of those terms rather
than the finished number, which is what makes them separable — a chamber-scoped
excursion reaches only the wafers that ran in that chamber, and a gauge drift
reaches every parameter that gauge measures and no others.

Nothing here reads a clock, a global random generator, or a filesystem. Given a
configuration and a seed the output is a pure function of its inputs, which is
what makes a dataset reproducible (DATASET_GUIDE.md §4.4).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid5

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from spc_platform.common.time import Clock
from spc_platform.config.reference import ReferenceData
from spc_platform.domain.enums import MeasurementStatus, SpatialSignature
from spc_platform.domain.ids import CodeRevision, LotId, ParameterId, ProductId, StepId, ToolId
from spc_platform.simulation import faults as fault_rules
from spc_platform.simulation.faults import FaultScope, ResolvedFault
from spc_platform.simulation.manifests import (
    GENERATOR_VERSION,
    DatasetManifest,
    FaultRecord,
    MessinessRecord,
    dataset_revision_for,
    scale_key,
)
from spc_platform.simulation.models import GeneratorConfig, ValueDistribution
from spc_platform.simulation.seeds import derive_generator, derive_uuid_namespace_key
from spc_platform.simulation.spatial import sampling_plan, signature_profile
from spc_platform.simulation.topology import (
    Characteristic,
    Topology,
    build_topology,
    recipe_for,
)
from spc_platform.simulation.variance import (
    ComponentScales,
    fixed_offsets,
    resolve_scales,
    slot_profile,
)

SIMULATION_NAMESPACE = UUID("8f2b6d1e-4c7a-5e93-9a10-6d4b2f8c1e07")
"""Fixed UUIDv5 namespace, so a regenerated dataset carries identical keys."""

_POISSON_RATE_FLOOR = 0.1
"""Lower bound on a Poisson rate; a non-positive rate has no distribution."""

_INVALID_VALUE_SIGMAS = 4_000.0
"""How far an injected bad record is displaced, in gauge sigmas.

Absurd by design. A bad record has to be unambiguously bad — far enough out
that no range check could plausibly admit it and no analysis could mistake it
for an excursion — or the quarantine test it exists for would be testing the
threshold rather than the quarantine.
"""

_STRING_COLUMNS = (
    "lot_id",
    "wafer_id",
    "parameter_id",
    "unit",
    "step_id",
    "tool_id",
    "chamber_id",
    "recipe_id",
    "product_id",
    "metrology_tool_id",
)

RAW_COLUMNS = (
    "measurement_id",
    "timestamp",
    "lot_id",
    "wafer_id",
    "slot",
    "site_id",
    "site_x",
    "site_y",
    "parameter_id",
    "value",
    "unit",
    "step_id",
    "tool_id",
    "chamber_id",
    "recipe_id",
    "product_id",
    "metrology_tool_id",
    "measurement_status",
)
"""Columns of the raw zone, in the order the generator writes them."""


@dataclass(frozen=True, slots=True)
class LotPlan:
    """One lot: what it is, and when it started."""

    lot_index: int
    lot_id: LotId
    product_id: ProductId
    started_at: datetime


@dataclass(frozen=True, slots=True)
class GeneratedDataset:
    """A generated dataset and the ground truth that describes it."""

    frame: pd.DataFrame
    manifest: DatasetManifest


def _schedule_lots(config: GeneratorConfig) -> tuple[LotPlan, ...]:
    """Lay out the lot sequence, assigning products by the configured mix."""
    schedule = config.schedule
    products = [entry.product_id for entry in config.product_mix]
    weights = np.asarray([entry.weight for entry in config.product_mix], dtype=np.float64)
    probabilities = weights / weights.sum()

    generator = derive_generator(config.seed, "product_mix")
    chosen = generator.choice(len(products), size=schedule.lots, p=probabilities)

    start = schedule.start_at.astimezone(UTC)
    return tuple(
        LotPlan(
            lot_index=index,
            lot_id=LotId(f"LOT-{index + 1:05d}"),
            product_id=products[int(chosen[index])],
            started_at=start + timedelta(minutes=schedule.lot_interval_minutes * index),
        )
        for index in range(schedule.lots)
    )


def _measured_slots(sample_size: int, wafers_per_lot: int) -> NDArray[np.int_]:
    """Return the monitor slots for a characteristic, spread across the carrier.

    Fixed rather than resampled per lot, because a fab measures named monitor
    slots. That makes the slot effect a systematic within-lot profile — visible
    on a multi-wafer subgroup, absorbed into the level on a single-wafer one —
    rather than an extra source of noise.
    """
    if sample_size <= 1:
        return np.asarray([(wafers_per_lot + 1) // 2], dtype=np.int_)
    positions = np.linspace(1.0, float(wafers_per_lot), sample_size)
    return np.unique(np.round(positions).astype(np.int_))


@dataclass(frozen=True, slots=True)
class _Fleet:
    """Persistent offsets for the equipment serving one characteristic."""

    tools: tuple[ToolId, ...]
    tool_offsets: Mapping[str, float]
    chamber_offsets: Mapping[str, float]


def _build_fleet(
    characteristic: Characteristic,
    topology: Topology,
    scales: ComponentScales,
    seed: int,
) -> _Fleet:
    """Draw the fixed tool and chamber offsets for one characteristic.

    Offsets are keyed by product as well as parameter. A tool's bias is a
    property of the recipe it runs, and recipes are per product, so the same
    chamber may sit high on one device and on target on another.
    """
    tools = topology.tools_by_step[characteristic.step_id]
    scope = f"{characteristic.parameter_id}|{characteristic.product_id}"
    tool_offsets = fixed_offsets(
        tuple(str(tool) for tool in tools),
        scales.sigma_tool_offset,
        master_seed=seed,
        stream=f"tool_offset|{scope}",
    )
    chamber_offsets: dict[str, float] = {}
    for tool in tools:
        chambers = topology.chambers_by_tool[tool]
        chamber_offsets.update(
            fixed_offsets(
                tuple(str(chamber) for chamber in chambers),
                scales.sigma_chamber_offset,
                master_seed=seed,
                stream=f"chamber_offset|{scope}|{tool}",
            )
        )
    return _Fleet(tools=tools, tool_offsets=tool_offsets, chamber_offsets=chamber_offsets)


def _tool_for_lot(
    tools: Sequence[ToolId],
    *,
    seed: int,
    lot_index: int,
    step_id: StepId,
) -> ToolId:
    """Choose the tool a lot ran on at a step.

    Keyed on the lot and step rather than on the parameter, because a lot ran on
    one tool at that step and every parameter measured there reflects it. Keying
    per parameter would break the tool commonality that root cause analysis
    exists to find.
    """
    generator = derive_generator(seed, "tool_choice", step_id, lot_index)
    return tools[int(generator.integers(len(tools)))]


@dataclass(frozen=True, slots=True)
class _BlockArrays:
    """Column arrays for one lot's measurements of one characteristic."""

    values: NDArray[np.float64]
    truth: NDArray[np.float64]
    slots: NDArray[np.int_]
    chambers: NDArray[np.object_]
    site_ids: NDArray[np.int_]
    site_x: NDArray[np.float64]
    site_y: NDArray[np.float64]
    timestamps: NDArray[np.datetime64]
    outlier_count: int


@dataclass(frozen=True, slots=True)
class _BlockInputs:
    """Everything one block of measurements is generated from."""

    characteristic: Characteristic
    lot: LotPlan
    scales: ComponentScales
    fleet: _Fleet
    tool_id: ToolId
    metrology_tool_id: str
    faults: Sequence[ResolvedFault]
    lot_count: int


def _generate_block(
    inputs: _BlockInputs,
    config: GeneratorConfig,
    topology: Topology,
) -> _BlockArrays:
    """Compose one lot's measurements of one characteristic."""
    characteristic = inputs.characteristic
    scales = inputs.scales
    seed = config.seed
    wafers_per_lot = config.schedule.wafers_per_lot

    slots = _measured_slots(characteristic.sample_size, wafers_per_lot)
    coordinates = sampling_plan(characteristic.parameter.sampling_sites)
    wafer_count = slots.shape[0]
    site_count = coordinates.shape[0]

    stream = (characteristic.parameter_id, characteristic.product_id, inputs.lot.lot_index)

    # Chambers are assigned per wafer: a multi-chamber tool splits a lot across
    # its chambers, which is what makes chamber mismatch visible within one lot
    # rather than only between them.
    chamber_pool = topology.chambers_by_tool[inputs.tool_id]
    chamber_rng = derive_generator(seed, "chamber_choice", inputs.tool_id, *stream)
    chamber_index = np.asarray(chamber_rng.integers(len(chamber_pool), size=wafer_count))
    chamber_names = [str(chamber_pool[int(index)]) for index in chamber_index]
    chambers: NDArray[np.object_] = np.asarray(chamber_names, dtype=object)

    lot_effect = float(derive_generator(seed, "lot_effect", *stream).normal(0.0, scales.sigma_lot))
    tool_offset = inputs.fleet.tool_offsets[str(inputs.tool_id)]
    chamber_offset = np.asarray(
        [inputs.fleet.chamber_offsets[name] for name in chamber_names],
        dtype=np.float64,
    )
    slot_effect = slot_profile(slots, scales.slot_amplitude, wafers_per_lot=wafers_per_lot)

    # One fault effect per distinct chamber, since a chamber-scoped fault must
    # reach only the wafers that ran in it.
    effects = {
        chamber: fault_rules.combine(
            inputs.faults,
            FaultScope(
                parameter_id=characteristic.parameter_id,
                product_id=characteristic.product_id,
                tool_id=inputs.tool_id,
                chamber_id=chamber,
                metrology_tool_id=inputs.metrology_tool_id,  # type: ignore[arg-type]
            ),
            lot_index=inputs.lot.lot_index,
            lot_count=inputs.lot_count,
            sigma=scales.sigma_total,
        )
        for chamber in dict.fromkeys(chambers)
    }
    fault_level = np.asarray([effects[c].level_offset for c in chambers], dtype=np.float64)
    gauge_shift = np.asarray([effects[c].gauge_offset for c in chambers], dtype=np.float64)
    # The fault declares a factor on the *variance*, so the factor on sigma is
    # its square root. Applying it to sigma directly would make a manifest
    # reading 2.2 describe a fourfold variance increase, and every score taken
    # against that number would be wrong by a square.
    sigma_scale = np.sqrt(
        np.asarray(
            [effects[c].process_variance_multiplier for c in chambers],
            dtype=np.float64,
        )
    )

    spatial = np.stack(
        [
            signature_profile(
                effects[chamber].spatial_override
                or characteristic_signature(config, characteristic),
                coordinates,
                scales.spatial_amplitude * effects[chamber].spatial_amplitude_multiplier,
            )
            for chamber in chambers
        ]
    )

    wafer_effect = (
        derive_generator(seed, "wafer_effect", *stream).normal(0.0, 1.0, wafer_count)
        * scales.sigma_wafer
        * sigma_scale
    )

    level = (
        scales.target
        + lot_effect
        + tool_offset
        + chamber_offset
        + slot_effect
        + wafer_effect
        + fault_level
    )

    physics = config.physics_for(characteristic.parameter_id)
    if physics.distribution is ValueDistribution.POISSON:
        rate = np.maximum(level[:, None] + spatial + gauge_shift[:, None], _POISSON_RATE_FLOOR)
        observed = derive_generator(seed, "poisson", *stream).poisson(rate).astype(np.float64)
        truth = rate
    else:
        site_residual = (
            derive_generator(seed, "site_residual", *stream).normal(
                0.0, 1.0, (wafer_count, site_count)
            )
            * scales.sigma_site
            * sigma_scale[:, None]
        )
        truth = level[:, None] + spatial + site_residual
        gauge_error = derive_generator(seed, "gauge_error", *stream).normal(
            0.0, scales.sigma_gauge, (wafer_count, site_count)
        )
        observed = truth + gauge_error + gauge_shift[:, None]

    observed, outlier_count = _apply_outliers(
        observed,
        effects=effects,
        chambers=chambers,
        seed=seed,
        stream=stream,
    )

    timestamps = _block_timestamps(inputs, config, topology, wafer_count=wafer_count)

    return _BlockArrays(
        values=observed.reshape(-1),
        truth=np.broadcast_to(truth, observed.shape).reshape(-1).copy(),
        slots=np.repeat(slots, site_count),
        chambers=np.repeat(chambers, site_count),
        site_ids=np.tile(np.arange(1, site_count + 1, dtype=np.int_), wafer_count),
        site_x=np.tile(coordinates[:, 0], wafer_count),
        site_y=np.tile(coordinates[:, 1], wafer_count),
        timestamps=np.repeat(timestamps, site_count),
        outlier_count=outlier_count,
    )


def characteristic_signature(
    config: GeneratorConfig,
    characteristic: Characteristic,
) -> SpatialSignature:
    """Return the baseline spatial signature configured for a characteristic."""
    return config.physics_for(characteristic.parameter_id).spatial_signature


def _apply_outliers(
    observed: NDArray[np.float64],
    *,
    effects: Mapping[object, fault_rules.FaultEffect],
    chambers: NDArray[np.object_],
    seed: int,
    stream: tuple[object, ...],
) -> tuple[NDArray[np.float64], int]:
    """Add gross errors where an outlier fault is active.

    Outliers are emitted as ordinary valid measurements. Flagging them at
    generation would hand the platform the answer: an outlier may be the
    excursion the whole system exists to detect, and deciding whether it is one
    is the platform's job (DATASET_GUIDE.md §5).
    """
    if not any(effects[chamber].outliers for chamber in dict.fromkeys(chambers)):
        return observed, 0

    result = observed.copy()
    total = 0
    # Per chamber, because an outlier source is scoped like any other fault and
    # a lot is split across the chambers of its tool. Iterating the chambers
    # without restricting the rows would apply one source several times over the
    # whole block, inflating both the magnitude and the count the manifest
    # records — and the manifest is what the platform is scored against.
    for chamber in dict.fromkeys(chambers):
        in_chamber = (chambers == chamber)[:, None]
        for spec in effects[chamber].outliers:
            generator = derive_generator(seed, "outlier", spec.fault_id, chamber, *stream)
            mask = (generator.random(result.shape) < spec.rate) & in_chamber
            signs = generator.choice(np.asarray([-1.0, 1.0]), size=result.shape)
            result = result + mask * signs * spec.magnitude
            total += int(mask.sum())
    return result, total


def _block_timestamps(
    inputs: _BlockInputs,
    config: GeneratorConfig,
    topology: Topology,
    *,
    wafer_count: int,
) -> NDArray[np.datetime64]:
    """Return one naive-UTC timestamp per measured wafer, in route order."""
    schedule = config.schedule
    position = topology.step_positions[inputs.characteristic.step_id]
    base = inputs.lot.started_at.astimezone(UTC).replace(tzinfo=None) + timedelta(
        minutes=schedule.step_interval_minutes * position
    )
    offsets = np.arange(wafer_count, dtype="int64") * np.timedelta64(
        schedule.wafer_interval_seconds, "s"
    )
    return np.datetime64(base, "ns") + offsets.astype("timedelta64[s]")


def _resolve_all_scales(
    config: GeneratorConfig,
    topology: Topology,
) -> dict[tuple[ParameterId, ProductId], ComponentScales]:
    """Resolve absolute sigmas once per characteristic, at the dataset start."""
    resolved: dict[tuple[ParameterId, ProductId], ComponentScales] = {}
    for product, characteristics in topology.characteristics_by_product.items():
        for characteristic in characteristics:
            physics = config.physics_for(characteristic.parameter_id)
            spec = topology.specification_at(
                (characteristic.parameter_id, product, characteristic.step_id),
                config.schedule.start_at,
            )
            resolved[(characteristic.parameter_id, product)] = resolve_scales(
                physics,
                config.variance_for(physics),
                spec,
            )
    return resolved


def _fault_records(
    resolved: Sequence[ResolvedFault],
    scales: Mapping[tuple[ParameterId, ProductId], ComponentScales],
) -> tuple[FaultRecord, ...]:
    """Turn resolved faults into the manifest's ground-truth rows."""
    records: list[FaultRecord] = []
    for fault in resolved:
        spec = fault.spec
        absolute: float | None = None
        unit = None
        if spec.parameter_id is not None and spec.product_id is not None:
            scale = scales.get((spec.parameter_id, spec.product_id))
            if scale is not None:
                absolute = spec.magnitude_sigma * scale.sigma_total
                unit = scale.unit
        records.append(
            FaultRecord(
                fault_id=spec.fault_id,
                kind=spec.kind,
                parameter_id=spec.parameter_id,
                product_id=spec.product_id,
                tool_id=spec.tool_id,
                chamber_id=spec.chamber_id,
                metrology_tool_id=spec.metrology_tool_id,
                onset_lot_index=fault.onset_lot_index,
                onset_at=fault.onset_at.astimezone(UTC),
                magnitude_sigma=spec.magnitude_sigma,
                magnitude_absolute=absolute,
                unit=unit,
                period_lots=spec.period_lots,
                variance_factor=spec.variance_factor,
                signature=spec.signature,
                note=spec.note,
            )
        )
    return tuple(records)


def _offsets_by_characteristic(
    fleets: Mapping[tuple[ParameterId, ProductId], _Fleet],
    select: Callable[[_Fleet], Mapping[str, float]],
) -> dict[str, dict[str, float]]:
    """Collect one fleet's fixed offsets per characteristic, for the manifest."""
    return {
        scale_key(parameter_id, product_id): dict(sorted(select(fleet).items()))
        for (parameter_id, product_id), fleet in sorted(
            fleets.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))
        )
    }


def generate_dataset(
    config: GeneratorConfig,
    reference: ReferenceData,
    *,
    code_revision: CodeRevision,
    clock: Clock,
) -> GeneratedDataset:
    """Generate one dataset and the manifest that describes it.

    Parameters
    ----------
    config
        The generator configuration. With ``config.seed`` it fully determines
        the measurements.
    reference
        Committed reference data: the fab this dataset is generated for.
    code_revision
        Revision of the code producing the dataset, recorded in the manifest so
        a result can be traced to the generator that made it.
    clock
        Injected time source, used only for the manifest's ``generated_at``.
        No measurement timestamp comes from it — those are derived from the
        configured schedule, so the data does not change with the wall clock.

    Returns
    -------
    GeneratedDataset
        The measurement frame in raw-zone column order, and its manifest.
    """
    topology = build_topology(reference, config)
    lots = _schedule_lots(config)
    resolved_faults = fault_rules.resolve_faults(config, [lot.started_at for lot in lots])
    scales = _resolve_all_scales(config, topology)

    fleets = {
        (characteristic.parameter_id, product): _build_fleet(
            characteristic,
            topology,
            scales[(characteristic.parameter_id, product)],
            config.seed,
        )
        for product, characteristics in topology.characteristics_by_product.items()
        for characteristic in characteristics
    }

    blocks: list[_BlockArrays] = []
    identity: list[tuple[LotPlan, Characteristic, ToolId, str, int]] = []
    outliers = 0

    for lot in lots:
        for characteristic in topology.characteristics_by_product[lot.product_id]:
            if not characteristic.is_due(lot.lot_index):
                continue
            key = (characteristic.parameter_id, lot.product_id)
            fleet = fleets[key]
            tool_id = _tool_for_lot(
                fleet.tools,
                seed=config.seed,
                lot_index=lot.lot_index,
                step_id=characteristic.step_id,
            )
            gauges = topology.gauges_for(characteristic.parameter.metrology_method)
            gauge_rng = derive_generator(
                config.seed,
                "gauge_choice",
                characteristic.parameter_id,
                lot.lot_index,
            )
            metrology_tool_id = str(gauges[int(gauge_rng.integers(len(gauges)))])

            block = _generate_block(
                _BlockInputs(
                    characteristic=characteristic,
                    lot=lot,
                    scales=scales[key],
                    fleet=fleet,
                    tool_id=tool_id,
                    metrology_tool_id=metrology_tool_id,
                    faults=resolved_faults,
                    lot_count=len(lots),
                ),
                config,
                topology,
            )
            blocks.append(block)
            identity.append((lot, characteristic, tool_id, metrology_tool_id, block.values.size))
            outliers += block.outlier_count

    frame = _assemble_frame(blocks, identity, scales)
    frame, messiness = _apply_messiness(frame, config, outlier_points=outliers)
    frame = _finalise(frame, config)

    config_revision = config.revision()
    manifest = DatasetManifest(
        dataset_id=config.dataset_id,
        generated_at=clock.now().astimezone(UTC),
        generator_version=GENERATOR_VERSION,
        seed=config.seed,
        code_revision=code_revision,
        config_revision=config_revision,
        dataset_revision=dataset_revision_for(config.dataset_id, config_revision, config.seed),
        row_count=len(frame),
        content_digest="",
        config=config,
        faults=_fault_records(resolved_faults, scales),
        messiness=messiness,
        component_scales={
            scale_key(parameter_id, product_id): scale.as_dict()
            for (parameter_id, product_id), scale in sorted(
                scales.items(), key=lambda item: (str(item[0][0]), str(item[0][1]))
            )
        },
        tool_offsets=_offsets_by_characteristic(fleets, lambda fleet: fleet.tool_offsets),
        chamber_offsets=_offsets_by_characteristic(fleets, lambda fleet: fleet.chamber_offsets),
    )
    return GeneratedDataset(frame=frame, manifest=manifest)


def _assemble_frame(
    blocks: Sequence[_BlockArrays],
    identity: Sequence[tuple[LotPlan, Characteristic, ToolId, str, int]],
    scales: Mapping[tuple[ParameterId, ProductId], ComponentScales],
) -> pd.DataFrame:
    """Concatenate the generated blocks into one frame in deterministic order."""
    if not blocks:
        return pd.DataFrame(columns=[*RAW_COLUMNS, "truth", "sigma_gauge"])

    def repeated(index: int, value: str) -> NDArray[np.object_]:
        return np.full(identity[index][4], value, dtype=object)

    frame = pd.DataFrame(
        {
            "timestamp": np.concatenate([block.timestamps for block in blocks]),
            "lot_id": np.concatenate(
                [repeated(i, str(item[0].lot_id)) for i, item in enumerate(identity)]
            ),
            "slot": np.concatenate([block.slots for block in blocks]),
            "site_id": np.concatenate([block.site_ids for block in blocks]),
            "site_x": np.concatenate([block.site_x for block in blocks]),
            "site_y": np.concatenate([block.site_y for block in blocks]),
            "parameter_id": np.concatenate(
                [repeated(i, str(item[1].parameter_id)) for i, item in enumerate(identity)]
            ),
            "value": np.concatenate([block.values for block in blocks]),
            "unit": np.concatenate(
                [
                    repeated(i, str(scales[(item[1].parameter_id, item[0].product_id)].unit))
                    for i, item in enumerate(identity)
                ]
            ),
            "step_id": np.concatenate(
                [repeated(i, str(item[1].step_id)) for i, item in enumerate(identity)]
            ),
            "tool_id": np.concatenate(
                [repeated(i, str(item[2])) for i, item in enumerate(identity)]
            ),
            "chamber_id": np.concatenate([block.chambers for block in blocks]),
            "product_id": np.concatenate(
                [repeated(i, str(item[0].product_id)) for i, item in enumerate(identity)]
            ),
            "metrology_tool_id": np.concatenate(
                [repeated(i, str(item[3])) for i, item in enumerate(identity)]
            ),
            "truth": np.concatenate([block.truth for block in blocks]),
            "sigma_gauge": np.concatenate(
                [
                    np.full(
                        item[4],
                        scales[(item[1].parameter_id, item[0].product_id)].sigma_gauge,
                    )
                    for i, item in enumerate(identity)
                ]
            ),
        }
    )
    frame["wafer_id"] = frame["lot_id"] + ":" + frame["slot"].astype(str)
    frame["recipe_id"] = [
        str(recipe_for(StepId(step), ProductId(product)))
        for step, product in zip(frame["step_id"], frame["product_id"], strict=True)
    ]
    frame["measurement_status"] = str(MeasurementStatus.VALID)
    return frame.sort_values(
        ["timestamp", "lot_id", "parameter_id", "slot", "site_id"],
        kind="stable",
        ignore_index=True,
    )


def _remeasured_values(
    repeat: pd.DataFrame,
    config: GeneratorConfig,
    generator: np.random.Generator,
) -> NDArray[np.float64]:
    """Re-read the same wafers, drawing from each parameter's own distribution.

    A remeasurement is a second visit to the metrology tool, so it re-draws the
    gauge error around the unchanged truth. Counts have to be re-drawn as
    counts: adding Gaussian gauge noise to a defect count yields 20.4 defects,
    which no inspector ever reported and which would make the parameter's
    distribution a property of whether the wafer happened to be remeasured.
    """
    truth = repeat["truth"].to_numpy(dtype=np.float64)
    gauge = repeat["sigma_gauge"].to_numpy(dtype=np.float64)
    values: NDArray[np.float64] = truth + generator.normal(0.0, 1.0, len(repeat)) * gauge

    counted = (
        repeat["parameter_id"]
        .isin(
            {
                str(physics.parameter_id)
                for physics in config.parameters
                if physics.distribution is ValueDistribution.POISSON
            }
        )
        .to_numpy()
    )
    if counted.any():
        values[counted] = generator.poisson(np.maximum(truth[counted], _POISSON_RATE_FLOOR)).astype(
            np.float64
        )
    return values


def _apply_messiness(
    frame: pd.DataFrame,
    config: GeneratorConfig,
    *,
    outlier_points: int,
) -> tuple[pd.DataFrame, MessinessRecord]:
    """Reproduce the data-quality situations the platform must survive.

    Re-measurement retains both records, the superseded one marked rather than
    deleted. Missing measurements are simply absent — never imputed, because an
    imputed point on a control chart is a fabricated signal (DATASET_GUIDE.md
    §5).

    Losses are applied before remeasurements, so that every count below
    describes the dataset that is delivered rather than an intermediate state.
    It is also the more faithful order: a result that was never recorded is not
    a result anyone sends back to the metrology tool.
    """
    messiness = config.messiness
    before = len(frame)
    generator = derive_generator(config.seed, "messiness")

    frame = frame.copy()
    missing = 0
    if messiness.missing_rate > 0.0 and before:
        keep = generator.random(before) >= messiness.missing_rate
        missing = int((~keep).sum())
        frame = frame[keep].reset_index(drop=True)

    superseded = 0
    remeasurement_events = 0

    if messiness.remeasurement_rate > 0.0 and len(frame):
        group_keys = frame["lot_id"] + "|" + frame["parameter_id"] + "|" + frame["wafer_id"]
        unique_groups = np.asarray(pd.unique(group_keys), dtype=object)
        selected = unique_groups[
            generator.random(unique_groups.shape[0]) < messiness.remeasurement_rate
        ]
        if selected.size:
            mask = group_keys.isin(set(selected))
            original = frame[mask]
            repeat = original.copy()
            repeat["timestamp"] = repeat["timestamp"] + pd.Timedelta(hours=2)
            repeat["value"] = _remeasured_values(repeat, config, generator)
            frame.loc[mask, "measurement_status"] = str(MeasurementStatus.SUPERSEDED)
            superseded = int(mask.sum())
            remeasurement_events = int(selected.size)
            frame = pd.concat([frame, repeat], ignore_index=True)

    invalid = 0
    if messiness.invalid_record_rate > 0.0 and len(frame):
        corrupt = generator.random(len(frame)) < messiness.invalid_record_rate
        invalid = int(corrupt.sum())
        if invalid:
            frame.loc[corrupt, "value"] += _INVALID_VALUE_SIGMAS * frame.loc[corrupt, "sigma_gauge"]

    record = MessinessRecord(
        measurements_before_messiness=before,
        remeasurement_events=remeasurement_events,
        superseded_records=superseded,
        missing_measurements=missing,
        invalid_records=invalid,
        outlier_points=outlier_points,
    )
    return frame, record


def _finalise(frame: pd.DataFrame, config: GeneratorConfig) -> pd.DataFrame:
    """Sort, assign deterministic identifiers, and reduce to the raw-zone columns."""
    frame = frame.sort_values(
        ["timestamp", "lot_id", "parameter_id", "slot", "site_id", "measurement_status"],
        kind="stable",
        ignore_index=True,
    )
    occurrence = frame.groupby(
        ["lot_id", "parameter_id", "wafer_id", "site_id"], sort=False
    ).cumcount()
    frame["measurement_id"] = [
        str(
            uuid5(
                SIMULATION_NAMESPACE,
                derive_uuid_namespace_key(config.dataset_id, lot, parameter, wafer, site, index),
            )
        )
        for lot, parameter, wafer, site, index in zip(
            frame["lot_id"],
            frame["parameter_id"],
            frame["wafer_id"],
            frame["site_id"],
            occurrence,
            strict=True,
        )
    ]
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    for column in _STRING_COLUMNS:
        frame[column] = frame[column].astype(str)
    frame["slot"] = frame["slot"].astype("int64")
    frame["site_id"] = frame["site_id"].astype("int64")
    return frame.loc[:, list(RAW_COLUMNS)].reset_index(drop=True)
