"""Build rational subgroups from an analysis-ready series (FR-C04).

Subgrouping collapses the site grain into chart points. The processed zone
keeps every site row; this function is the handoff used by charting use cases.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from spc_platform.common.errors import InsufficientDataError, SubgroupingError
from spc_platform.domain.enums import SubgroupingKind
from spc_platform.domain.ids import LotId, WaferId
from spc_platform.domain.measurement import Measurement
from spc_platform.domain.measurement_series import MeasurementSeries
from spc_platform.domain.subgrouping import Subgroup, SubgroupingStrategy


def build_subgroups(
    series: MeasurementSeries,
    strategy: SubgroupingStrategy,
    *,
    minimum_size: int = 1,
) -> tuple[Subgroup, ...]:
    """Group ``series`` according to ``strategy``, stamping the strategy on each.

    ``SITES_AS_SUBGROUP`` is refused unless ``explicitly_declared`` is true
    (enforced on the strategy value object). ``WAFER_MEAN`` is the default path
    for site-level metrology.
    """
    if strategy.kind is SubgroupingKind.SITES_AS_SUBGROUP:
        return _sites_as_subgroups(series, strategy, minimum_size=minimum_size)
    if strategy.kind is SubgroupingKind.WAFER_MEAN:
        return _wafer_means(series, strategy, minimum_size=minimum_size)
    if strategy.kind is SubgroupingKind.LOT_MEAN:
        return _lot_means(series, strategy, minimum_size=minimum_size)
    raise SubgroupingError(
        "subgrouping kind is not implemented for this series shape",
        kind=strategy.kind.value,
    )


def _sites_as_subgroups(
    series: MeasurementSeries,
    strategy: SubgroupingStrategy,
    *,
    minimum_size: int,
) -> tuple[Subgroup, ...]:
    """Each measurement is its own subgroup of size one."""
    if minimum_size > 1:
        raise InsufficientDataError(
            "sites-as-subgroup cannot satisfy minimum_size > 1",
            minimum_size=minimum_size,
        )
    return tuple(
        Subgroup(
            parameter_id=series.parameter_id,
            strategy=strategy,
            values=(item.value,),
            timestamp=item.timestamp,
            lot_id=item.lot_id,
            wafer_id=item.wafer_id,
        )
        for item in series.measurements
    )


def _wafer_means(
    series: MeasurementSeries,
    strategy: SubgroupingStrategy,
    *,
    minimum_size: int,
) -> tuple[Subgroup, ...]:
    """One subgroup per wafer: the mean of its site values."""
    buckets: dict[tuple[str, str], list[Measurement]] = defaultdict(list)
    for item in series.measurements:
        if item.measurement_status.value == "superseded":
            continue
        buckets[(str(item.lot_id), str(item.wafer_id))].append(item)

    subgroups: list[Subgroup] = []
    for (lot_id, wafer_id), items in sorted(buckets.items(), key=lambda pair: pair[0]):
        if len(items) < minimum_size:
            raise InsufficientDataError(
                "wafer subgroup below configured minimum size",
                lot_id=lot_id,
                wafer_id=wafer_id,
                size=len(items),
                minimum_size=minimum_size,
            )
        ordered = sorted(items, key=lambda measurement: measurement.timestamp)
        mean = sum(item.value for item in ordered) / len(ordered)
        subgroups.append(
            Subgroup(
                parameter_id=series.parameter_id,
                strategy=strategy,
                values=(mean,),
                timestamp=ordered[-1].timestamp,
                lot_id=LotId(lot_id),
                wafer_id=WaferId(wafer_id),
            )
        )
    if not subgroups:
        raise InsufficientDataError(
            "no non-superseded measurements available for subgrouping",
            parameter_id=str(series.parameter_id),
        )
    return tuple(subgroups)


def _lot_means(
    series: MeasurementSeries,
    strategy: SubgroupingStrategy,
    *,
    minimum_size: int,
) -> tuple[Subgroup, ...]:
    """One subgroup per lot: the mean of all non-superseded site values."""
    buckets: dict[str, list[Measurement]] = defaultdict(list)
    for item in series.measurements:
        if item.measurement_status.value == "superseded":
            continue
        buckets[str(item.lot_id)].append(item)

    subgroups: list[Subgroup] = []
    for lot_id, items in sorted(buckets.items()):
        if len(items) < minimum_size:
            raise InsufficientDataError(
                "lot subgroup below configured minimum size",
                lot_id=lot_id,
                size=len(items),
                minimum_size=minimum_size,
            )
        ordered = sorted(items, key=lambda measurement: measurement.timestamp)
        mean = sum(item.value for item in ordered) / len(ordered)
        subgroups.append(
            Subgroup(
                parameter_id=series.parameter_id,
                strategy=strategy,
                values=(mean,),
                timestamp=ordered[-1].timestamp,
                lot_id=LotId(lot_id),
                wafer_id=None,
            )
        )
    if not subgroups:
        raise InsufficientDataError(
            "no non-superseded measurements available for subgrouping",
            parameter_id=str(series.parameter_id),
        )
    return tuple(subgroups)


def active_measurements(measurements: Sequence[Measurement]) -> tuple[Measurement, ...]:
    """Return measurements that are not superseded."""
    return tuple(item for item in measurements if item.measurement_status.value != "superseded")
