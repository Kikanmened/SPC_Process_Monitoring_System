"""The structural invariants the layering rules are built on top of.

These are the cheapest tests in the repository and they defend two things that
are expensive to discover late: that every layer named in
SYSTEM_ARCHITECTURE.md §2 actually exists as an importable package, and that
importing the platform does nothing.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

import spc_platform

LAYER_PACKAGES = (
    "analytics",
    "api",
    "application",
    "cli",
    "common",
    "config",
    "domain",
    "infrastructure",
    "observability",
    "pipelines",
    "scheduler",
)

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("layer", LAYER_PACKAGES)
def test_layer_package_exists_and_documents_itself(layer: str) -> None:
    module = importlib.import_module(f"spc_platform.{layer}")
    assert module.__doc__, f"spc_platform.{layer} must state what belongs in it"


def test_distribution_ships_a_py_typed_marker() -> None:
    """Without this marker, every consumer silently sees the package as untyped."""
    package_root = Path(str(spc_platform.__file__)).parent
    assert (package_root / "py.typed").is_file()


def test_importing_the_platform_configures_no_logging() -> None:
    """CODING_STANDARDS.md §4: importing must not configure logging.

    Checked in a subprocess because pytest attaches its own handlers to the
    root logger, which would mask exactly the side effect being tested.
    """
    probe = f"""
import importlib
import logging
import sys

before = list(logging.root.handlers)
import spc_platform
for layer in {LAYER_PACKAGES!r}:
    importlib.import_module("spc_platform." + layer)
after = list(logging.root.handlers)

if before != after:
    sys.stderr.write("import added logging handlers: " + repr(after))
    raise SystemExit(1)
"""

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe],
        capture_output=True,
        check=False,
        cwd=REPO_ROOT,
        text=True,
    )
    assert result.returncode == 0, result.stderr
