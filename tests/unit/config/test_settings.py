"""Typed configuration: unknown keys raise (FR-CF02, US-D3)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from spc_platform.common import ConfigurationError
from spc_platform.config import Profile, load_reference_data, load_settings

REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.unit
def test_load_settings_from_committed_config() -> None:
    settings = load_settings(Profile.LOCAL, config_root=REPO_ROOT / "configs")
    assert settings.profile is Profile.LOCAL
    assert settings.platform.spc.capability.minimum_n == 25
    assert settings.config_revision
    registry = settings.unit_registry()
    assert registry.convert(1.0, source="um", target="nm") == 1000.0


@pytest.mark.unit
def test_unknown_configuration_key_raises(tmp_path: Path) -> None:
    base = tmp_path / "base"
    base.mkdir()
    (base / "platform.yaml").write_text(
        yaml.dump(
            {
                "name": "test",
                "timezone": "UTC",
                "units": {"units": ["nm"], "conversions": []},
                "typo_key": True,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "environments").mkdir()
    (tmp_path / "environments" / "local.yaml").write_text("{}\n", encoding="utf-8")

    with pytest.raises(ConfigurationError) as exc_info:
        load_settings(Profile.LOCAL, config_root=tmp_path)
    assert "validation" in str(exc_info.value).lower() or "typo" in str(exc_info.value)


@pytest.mark.unit
def test_settings_are_immutable() -> None:
    settings = load_settings(Profile.LOCAL, config_root=REPO_ROOT / "configs")
    with pytest.raises(ValidationError):
        settings.platform.name = "mutated"  # type: ignore[misc]


@pytest.mark.unit
def test_config_revision_changes_when_policy_changes(tmp_path: Path) -> None:
    def write(minimum_n: int) -> str:
        base = tmp_path / "base"
        base.mkdir(exist_ok=True)
        (base / "platform.yaml").write_text(
            yaml.dump(
                {
                    "name": "test",
                    "timezone": "UTC",
                    "units": {"units": ["nm"], "conversions": []},
                    "spc": {"capability": {"minimum_n": minimum_n}},
                }
            ),
            encoding="utf-8",
        )
        env = tmp_path / "environments"
        env.mkdir(exist_ok=True)
        (env / "local.yaml").write_text("{}\n", encoding="utf-8")
        return str(load_settings(Profile.LOCAL, config_root=tmp_path).config_revision)

    first = write(25)
    # rewrite with different n
    for child in (tmp_path / "base").iterdir():
        child.unlink()
    (tmp_path / "environments" / "local.yaml").unlink()
    (tmp_path / "environments").rmdir()
    second = write(50)
    assert first != second


@pytest.mark.unit
def test_load_reference_data_from_committed_files() -> None:
    reference = load_reference_data(REPO_ROOT / "data" / "reference")
    assert len(reference.parameters) >= 3
    assert len(reference.specification_limits) >= 3
    assert all(tool.chambers or tool.tool.is_metrology for tool in reference.tools)
    oxide = next(p for p in reference.parameters if p.parameter_id == "OXIDE_THK")
    assert oxide.unit == "nm"


@pytest.mark.unit
def test_unknown_key_in_reference_file_raises(tmp_path: Path) -> None:
    (tmp_path / "parameters.yaml").write_text(
        yaml.dump({"parameters": [], "unexpected": 1}),
        encoding="utf-8",
    )
    for name in (
        "specification_limits.yaml",
        "process_steps.yaml",
        "tools.yaml",
        "control_plans.yaml",
    ):
        key = name.removesuffix(".yaml")
        (tmp_path / name).write_text(yaml.dump({key: []}), encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_reference_data(tmp_path)
