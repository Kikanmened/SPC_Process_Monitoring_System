"""Unit registry and declared conversions.

A unit is never inferred from a magnitude. Conversion between units is
permitted only when both directions are declared in the registry (FR-D08).
"""

from __future__ import annotations

from dataclasses import dataclass

from spc_platform.common.errors import UnknownUnitError
from spc_platform.domain.ids import UnitSymbol


@dataclass(frozen=True, slots=True)
class UnitConversion:
    """A declared linear conversion: ``to = from * factor + offset``."""

    source: UnitSymbol
    target: UnitSymbol
    factor: float
    offset: float = 0.0

    def convert(self, value: float) -> float:
        """Apply the conversion to ``value``."""
        return value * self.factor + self.offset


@dataclass(frozen=True, slots=True)
class UnitRegistry:
    """The set of known units and the conversions between them."""

    units: frozenset[UnitSymbol]
    conversions: tuple[UnitConversion, ...]

    def __post_init__(self) -> None:
        """Reject conversions that reference unknown units or a zero factor."""
        for conversion in self.conversions:
            if conversion.source not in self.units:
                raise UnknownUnitError(
                    "conversion source is not a registered unit",
                    unit=str(conversion.source),
                )
            if conversion.target not in self.units:
                raise UnknownUnitError(
                    "conversion target is not a registered unit",
                    unit=str(conversion.target),
                )
            if conversion.factor == 0.0:
                raise UnknownUnitError(
                    "conversion factor must be non-zero",
                    source=str(conversion.source),
                    target=str(conversion.target),
                )

    def require(self, unit: UnitSymbol | str) -> UnitSymbol:
        """Return ``unit`` as a ``UnitSymbol`` if registered; else raise."""
        symbol = UnitSymbol(str(unit))
        if symbol not in self.units:
            raise UnknownUnitError("unit is not registered", unit=str(symbol))
        return symbol

    def convert(
        self,
        value: float,
        *,
        source: UnitSymbol | str,
        target: UnitSymbol | str,
    ) -> float:
        """Convert ``value`` from ``source`` to ``target``.

        Identity conversions (same unit) return ``value`` unchanged. No
        conversion is invented when none is declared.
        """
        source_unit = self.require(source)
        target_unit = self.require(target)
        if source_unit == target_unit:
            return value
        for conversion in self.conversions:
            if conversion.source == source_unit and conversion.target == target_unit:
                return conversion.convert(value)
        raise UnknownUnitError(
            "no declared conversion between units",
            source=str(source_unit),
            target=str(target_unit),
        )


def registry_from_declarations(
    units: list[str],
    conversions: list[dict[str, float | str]],
) -> UnitRegistry:
    """Build a registry from configuration declarations."""
    unit_set = frozenset(UnitSymbol(unit) for unit in units)
    parsed = tuple(
        UnitConversion(
            source=UnitSymbol(str(item["source"])),
            target=UnitSymbol(str(item["target"])),
            factor=float(item["factor"]),
            offset=float(item.get("offset", 0.0)),
        )
        for item in conversions
    )
    return UnitRegistry(units=unit_set, conversions=parsed)
