"""The interpreter pin is stated in two places, and they must agree.

ADR-0016 fixes one interpreter version: it is developed against, tested
against, and deployed. ``.python-version`` drives what `uv` installs;
``requires-python`` drives what the packaging metadata permits. If they drift,
CI validates a configuration that is never deployed, which produces confident
signal about nothing.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_python_version_file_satisfies_requires_python() -> None:
    pinned = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    metadata = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    requires_python = metadata["project"]["requires-python"]

    major, minor = (int(part) for part in pinned.split(".")[:2])
    assert requires_python == f">={major}.{minor},<{major}.{minor + 1}", (
        f".python-version pins {pinned}, but requires-python is {requires_python}"
    )


def test_ruff_targets_the_pinned_interpreter() -> None:
    pinned = (REPO_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    metadata = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    expected = "py" + pinned.replace(".", "")
    assert metadata["tool"]["ruff"]["target-version"] == expected
    assert metadata["tool"]["mypy"]["python_version"] == pinned
