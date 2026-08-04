"""Unit registry and timezone boundary rules."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from spc_platform.common import (
    FixedClock,
    NaiveDatetimeError,
    UnknownUnitError,
    registry_from_declarations,
    require_aware,
)


def _naive(year: int = 2025, month: int = 1, day: int = 1) -> datetime:
    """Construct a naive datetime deliberately — the case under test."""
    return datetime(year, month, day, 12, 0, 0)  # noqa: DTZ001


@pytest.mark.unit
def test_require_aware_rejects_naive_datetime() -> None:
    with pytest.raises(NaiveDatetimeError):
        require_aware(_naive(), field_name="timestamp")


@pytest.mark.unit
def test_require_aware_accepts_timezone_aware() -> None:
    value = datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert require_aware(value, field_name="timestamp") is value


@pytest.mark.unit
def test_fixed_clock_rejects_naive_instant() -> None:
    with pytest.raises(NaiveDatetimeError):
        FixedClock(_naive())


@pytest.mark.unit
def test_unknown_unit_raises() -> None:
    registry = registry_from_declarations(units=["nm"], conversions=[])
    with pytest.raises(UnknownUnitError):
        registry.require("furlong")


@pytest.mark.unit
def test_undeclared_conversion_raises() -> None:
    registry = registry_from_declarations(units=["nm", "um"], conversions=[])
    with pytest.raises(UnknownUnitError):
        registry.convert(1.0, source="um", target="nm")


@pytest.mark.unit
def test_declared_conversion_applies_factor() -> None:
    registry = registry_from_declarations(
        units=["nm", "um"],
        conversions=[{"source": "um", "target": "nm", "factor": 1000.0}],
    )
    assert registry.convert(1.5, source="um", target="nm") == 1500.0


@pytest.mark.unit
def test_identity_conversion_is_noop() -> None:
    registry = registry_from_declarations(units=["nm"], conversions=[])
    assert registry.convert(10.0, source="nm", target="nm") == 10.0
