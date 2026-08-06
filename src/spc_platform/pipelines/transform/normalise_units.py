"""Convert units explicitly via the registry (FR-D08)."""

from __future__ import annotations

from dataclasses import dataclass

from spc_platform.common.errors import UnitConversionError
from spc_platform.common.units import UnitRegistry
from spc_platform.domain.ids import ParameterId, UnitSymbol
from spc_platform.pipelines.stage import StageFrame, StageResult

_STAGE_NAME = "normalise_units"


@dataclass(frozen=True, slots=True)
class ParameterUnitTarget:
    """Declared unit a parameter must be published in."""

    parameter_id: ParameterId
    unit: UnitSymbol


class NormaliseUnits:
    """Convert each parameter's values to its declared unit when needed."""

    name = _STAGE_NAME

    def __init__(
        self,
        registry: UnitRegistry,
        targets: tuple[ParameterUnitTarget, ...],
    ) -> None:
        self._registry = registry
        self._targets = {target.parameter_id: target.unit for target in targets}

    def apply(self, stage_frame: StageFrame) -> StageResult:
        """Convert units in place on a copy; never infer a unit from magnitude."""
        frame = stage_frame.frame.copy()
        rows_in = len(frame)
        if frame.empty or not self._targets:
            return StageResult(
                frame=stage_frame,
                rows_in=rows_in,
                rows_out=rows_in,
            )

        conversions = 0
        for parameter_id, target_unit in self._targets.items():
            mask = frame["parameter_id"].astype(str) == str(parameter_id)
            if not bool(mask.any()):
                continue
            source_units = frame.loc[mask, "unit"].astype(str).unique()
            for source in source_units:
                source_unit = UnitSymbol(source)
                subset = mask & (frame["unit"].astype(str) == source)
                if source_unit == target_unit:
                    continue
                try:
                    converted = [
                        self._registry.convert(
                            float(value),
                            source=source_unit,
                            target=target_unit,
                        )
                        for value in frame.loc[subset, "value"].tolist()
                    ]
                except Exception as exc:
                    raise UnitConversionError(
                        "no declared conversion for parameter unit normalisation",
                        parameter_id=str(parameter_id),
                        source=str(source_unit),
                        target=str(target_unit),
                        reason=str(exc),
                    ) from exc
                frame.loc[subset, "value"] = converted
                frame.loc[subset, "unit"] = str(target_unit)
                conversions += int(subset.sum())

        note = f"converted_values={conversions}"
        outgoing = StageFrame(
            frame=frame.reset_index(drop=True),
            context=stage_frame.context,
            notes=(*stage_frame.notes, note),
        )
        return StageResult(
            frame=outgoing,
            rows_in=rows_in,
            rows_out=len(frame),
            transformations=(note,) if conversions else (),
        )
