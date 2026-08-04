"""Material hierarchy and Measurement invariants."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tests.factories.domain import a_measurement, aware

from spc_platform.domain import (
    DomainInvariantError,
    Lot,
    LotId,
    Site,
    SiteId,
    Wafer,
    WaferId,
)


@pytest.mark.unit
def test_wafer_slot_must_be_in_1_to_25() -> None:
    with pytest.raises(ValidationError):
        Wafer(wafer_id=WaferId("LOT-1:0"), lot_id=LotId("LOT-1"), slot=0)
    with pytest.raises(ValidationError):
        Wafer(wafer_id=WaferId("LOT-1:26"), lot_id=LotId("LOT-1"), slot=26)


@pytest.mark.unit
def test_wafer_id_must_match_lot_and_slot() -> None:
    with pytest.raises((ValidationError, DomainInvariantError)):
        Wafer(wafer_id=WaferId("OTHER:1"), lot_id=LotId("LOT-1"), slot=1)


@pytest.mark.unit
def test_site_must_lie_within_wafer_radius() -> None:
    with pytest.raises((ValidationError, DomainInvariantError)):
        Site(site_id=SiteId(1), site_x_mm=200.0, site_y_mm=0.0)


@pytest.mark.unit
def test_site_at_centre_is_valid() -> None:
    site = Site(site_id=SiteId(1), site_x_mm=0.0, site_y_mm=0.0)
    assert site.site_id == SiteId(1)


@pytest.mark.unit
def test_lot_construction() -> None:
    lot = Lot(lot_id=LotId("LOT-1"), product_id="DEV-A")
    assert lot.lot_id == LotId("LOT-1")


@pytest.mark.unit
def test_measurement_rejects_naive_timestamp() -> None:
    with pytest.raises((ValidationError, DomainInvariantError)):
        a_measurement(timestamp=aware().replace(tzinfo=None))


@pytest.mark.unit
def test_measurement_rejects_slot_out_of_range() -> None:
    with pytest.raises((ValidationError, DomainInvariantError)):
        a_measurement(slot=26)


@pytest.mark.unit
def test_measurement_carries_unit_and_metrology_tool() -> None:
    measurement = a_measurement()
    assert measurement.unit == "nm"
    assert measurement.metrology_tool_id == "MET-ELLIP-01"
    assert measurement.chamber_id == "OX-01-A"
