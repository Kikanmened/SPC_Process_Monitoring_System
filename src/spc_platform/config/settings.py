"""Layered configuration parsed once into immutable typed models.

``base/`` supplies defaults; an environment overlay changes only what differs.
Unknown keys are errors (FR-CF02). No module elsewhere reads YAML.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from spc_platform.common.errors import ConfigurationError
from spc_platform.common.units import UnitRegistry, registry_from_declarations
from spc_platform.config.profiles import Profile
from spc_platform.config.revision import compute_config_revision
from spc_platform.domain.ids import ConfigRevision

_DEFAULT_CONFIG_ROOT = Path("configs")


class UnitsConfig(BaseModel):
    """Declared units and conversions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    units: list[str] = Field(min_length=1)
    conversions: list[dict[str, float | str]] = Field(default_factory=list)


class CapabilityPolicyConfig(BaseModel):
    """Policy for capability reporting refusals and minimum n."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_n: int = Field(ge=2, default=25)
    refuse_if_unstable: bool = True


class BaselinePolicyConfig(BaseModel):
    """Policy for qualifying a baseline window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_n: int = Field(ge=2, default=25)
    exclude_engineering_time: bool = True


class SpcPolicyConfig(BaseModel):
    """Statistical policy defaults (chart/rule specifics live under configs/spc/)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    capability: CapabilityPolicyConfig = Field(default_factory=CapabilityPolicyConfig)
    baseline: BaselinePolicyConfig = Field(default_factory=BaselinePolicyConfig)


class PlatformConfig(BaseModel):
    """Top-level platform settings shared by every environment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = "spc-platform"
    timezone: str = "UTC"
    units: UnitsConfig
    spc: SpcPolicyConfig = Field(default_factory=SpcPolicyConfig)


class Settings(BaseModel):
    """Immutable effective configuration for one process."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: Profile
    platform: PlatformConfig
    config_revision: ConfigRevision
    config_root: Path

    def unit_registry(self) -> UnitRegistry:
        """Build the unit registry from the effective configuration."""
        return registry_from_declarations(
            units=self.platform.units.units,
            conversions=self.platform.units.conversions,
        )


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigurationError("configuration file not found", path=str(path))
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            "configuration file is not valid YAML",
            path=str(path),
            reason=str(exc),
        ) from exc
    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigurationError(
            "configuration file must contain a mapping at the root",
            path=str(path),
        )
    return loaded


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(
    profile: Profile,
    *,
    config_root: Path | None = None,
) -> Settings:
    """Parse ``base/platform.yaml`` plus the profile overlay into ``Settings``.

    Parameters
    ----------
    profile
        Which environment overlay to apply.
    config_root
        Root of the ``configs/`` tree. Defaults to ``./configs``.
    """
    root = (config_root or _DEFAULT_CONFIG_ROOT).resolve()
    base_payload = _read_yaml(root / "base" / "platform.yaml")
    # Units may live alongside platform.yaml for readability.
    units_path = root / "base" / "units.yaml"
    if units_path.is_file():
        units_payload = _read_yaml(units_path)
        if "units" in base_payload:
            raise ConfigurationError(
                "units must be declared in units.yaml, not platform.yaml",
                path=str(root / "base" / "platform.yaml"),
            )
        base_payload = _deep_merge(base_payload, {"units": units_payload})

    overlay_path = root / "environments" / f"{profile.value}.yaml"
    overlay_payload = _read_yaml(overlay_path) if overlay_path.is_file() else {}
    effective = _deep_merge(base_payload, overlay_payload)

    try:
        platform = PlatformConfig.model_validate(effective)
    except Exception as exc:
        raise ConfigurationError(
            "configuration failed validation",
            profile=profile.value,
            reason=str(exc),
        ) from exc

    revision = compute_config_revision(platform.model_dump(mode="json"))
    return Settings(
        profile=profile,
        platform=platform,
        config_revision=revision,
        config_root=root,
    )
