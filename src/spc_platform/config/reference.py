"""Load committed reference data into typed domain objects.

Specification limits, parameters, tools, steps, and control plans are process
knowledge versioned in ``data/reference/`` (DATASET_GUIDE.md §3.2). Unknown
keys raise on load.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from spc_platform.common.errors import ConfigurationError
from spc_platform.domain.enums import ChartType, SubgroupingKind
from spc_platform.domain.equipment import Chamber, ProcessStep, Tool
from spc_platform.domain.ids import (
    ChamberId,
    OcapId,
    ParameterId,
    ProductId,
    StepId,
    ToolId,
    UnitSymbol,
)
from spc_platform.domain.parameter import Parameter
from spc_platform.domain.specification_limit import SpecificationLimit

_DEFAULT_REFERENCE_ROOT = Path("data/reference")


class ControlPlanCharacteristic(BaseModel):
    """One characteristic row of a control plan."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    product_id: ProductId
    step_id: StepId
    chart_type: ChartType
    sample_size: int = Field(ge=1)
    frequency: str
    ocap_id: OcapId
    rule_set_name: str


class ControlPlan(BaseModel):
    """A versioned control plan covering one or more characteristics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: str
    name: str
    characteristics: tuple[ControlPlanCharacteristic, ...] = Field(min_length=1)


class ToolRecord(BaseModel):
    """Tool plus its chambers, as declared in tools.yaml."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool: Tool
    chambers: tuple[Chamber, ...] = ()


class ReferenceData(BaseModel):
    """The full committed reference set for one fab model."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameters: tuple[Parameter, ...]
    specification_limits: tuple[SpecificationLimit, ...]
    tools: tuple[ToolRecord, ...]
    process_steps: tuple[ProcessStep, ...]
    control_plans: tuple[ControlPlan, ...]


def _read_yaml(path: Path) -> object:
    if not path.is_file():
        raise ConfigurationError("reference file not found", path=str(path))
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            "reference file is not valid YAML",
            path=str(path),
            reason=str(exc),
        ) from exc


def _require_list(payload: object, *, path: Path, key: str) -> list[object]:
    if not isinstance(payload, dict) or key not in payload:
        raise ConfigurationError(
            f"reference file must contain a '{key}' list",
            path=str(path),
        )
    items = payload[key]
    if not isinstance(items, list):
        raise ConfigurationError(
            f"'{key}' must be a list",
            path=str(path),
        )
    # Unknown top-level keys are errors.
    unexpected = set(payload) - {key}
    if unexpected:
        raise ConfigurationError(
            "unknown key in reference file",
            path=str(path),
            keys=sorted(unexpected),
        )
    return items


def load_reference_data(reference_root: Path | None = None) -> ReferenceData:
    """Load and validate every reference dataset under ``data/reference/``."""
    root = (reference_root or _DEFAULT_REFERENCE_ROOT).resolve()

    parameters = tuple(
        Parameter.model_validate(item)
        for item in _require_list(
            _read_yaml(root / "parameters.yaml"),
            path=root / "parameters.yaml",
            key="parameters",
        )
    )
    specification_limits = tuple(
        SpecificationLimit.model_validate(item)
        for item in _require_list(
            _read_yaml(root / "specification_limits.yaml"),
            path=root / "specification_limits.yaml",
            key="specification_limits",
        )
    )
    process_steps = tuple(
        ProcessStep.model_validate(item)
        for item in _require_list(
            _read_yaml(root / "process_steps.yaml"),
            path=root / "process_steps.yaml",
            key="process_steps",
        )
    )

    tools_payload = _require_list(
        _read_yaml(root / "tools.yaml"),
        path=root / "tools.yaml",
        key="tools",
    )
    tools: list[ToolRecord] = []
    for item in tools_payload:
        if not isinstance(item, dict):
            raise ConfigurationError("tool entry must be a mapping", path=str(root / "tools.yaml"))
        item_copy = dict(item)
        chambers_raw = item_copy.pop("chambers", [])
        if not isinstance(chambers_raw, list):
            raise ConfigurationError(
                "tool.chambers must be a list",
                path=str(root / "tools.yaml"),
            )
        tool = Tool.model_validate(item_copy)
        chambers = tuple(
            Chamber.model_validate({**chamber, "tool_id": str(tool.tool_id)})
            if "tool_id" not in chamber
            else Chamber.model_validate(chamber)
            for chamber in chambers_raw
        )
        for chamber in chambers:
            if chamber.tool_id != tool.tool_id:
                raise ConfigurationError(
                    "chamber.tool_id must match parent tool",
                    tool_id=str(tool.tool_id),
                    chamber_id=str(chamber.chamber_id),
                )
        tools.append(ToolRecord(tool=tool, chambers=chambers))

    plans_raw = _require_list(
        _read_yaml(root / "control_plans.yaml"),
        path=root / "control_plans.yaml",
        key="control_plans",
    )
    control_plans = tuple(ControlPlan.model_validate(item) for item in plans_raw)

    return ReferenceData(
        parameters=parameters,
        specification_limits=specification_limits,
        tools=tuple(tools),
        process_steps=process_steps,
        control_plans=control_plans,
    )


# Re-export enums used when authoring YAML so callers need one import surface.
__all__ = [
    "ChamberId",
    "ChartType",
    "ControlPlan",
    "ControlPlanCharacteristic",
    "ParameterId",
    "ReferenceData",
    "StepId",
    "SubgroupingKind",
    "ToolId",
    "ToolRecord",
    "UnitSymbol",
    "load_reference_data",
]
