"""Helpers for application-layer tests with a seeded local fake stack."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tests.factories.domain import a_baseline, a_measurement, a_specification_limit, aware

from spc_platform.common.time import FixedClock
from spc_platform.domain.ids import (
    ActorId,
    DataRevision,
    LotId,
    ParameterId,
    ProductId,
    SiteId,
    WaferId,
)
from spc_platform.infrastructure.composition import LocalBundle, build_local_bundle


def seeded_bundle(
    *,
    values: tuple[float, ...] = (10.0, 10.05, 9.98, 10.02, 10.01, 9.99, 10.03, 10.0),
    outlier: float | None = None,
    with_baseline: bool = True,
    with_specification: bool = True,
    fail_audit: bool = False,
) -> LocalBundle:
    """Build a local bundle with a short in-control series and optional outlier."""
    clock = FixedClock(datetime(2025, 7, 15, 12, 0, tzinfo=UTC))
    bundle = build_local_bundle(clock=clock, fail_audit_writes=fail_audit)
    revision = DataRevision("rev-app-1")
    start = aware(month=7, day=1)
    series_values = list(values)
    if outlier is not None:
        series_values.append(outlier)
    rows = []
    for index, value in enumerate(series_values):
        rows.append(
            a_measurement(
                data_revision=revision,
                value=value,
                timestamp=start + timedelta(hours=index),
                site_id=SiteId(index + 1),
                lot_id=LotId("LOT-001"),
                wafer_id=WaferId("LOT-001:1"),
                parameter_id=ParameterId("OXIDE_THK"),
                product_id=ProductId("DEV-A"),
            )
        )
    bundle.measurements.replace_revision(revision, tuple(rows))
    if with_baseline:
        bundle.baselines.save(
            a_baseline(
                parameter_id=ParameterId("OXIDE_THK"),
                effective_from=aware(month=6, day=1),
            )
        )
    if with_specification:
        bundle.specifications.save(
            a_specification_limit(
                parameter_id=ParameterId("OXIDE_THK"),
                product_id=ProductId("DEV-A"),
                effective_from=aware(month=1, day=1),
            )
        )
    return bundle


ACTOR = ActorId("qe.smith")
WINDOW_START = aware(month=7, day=1)
WINDOW_END = aware(month=7, day=14)
