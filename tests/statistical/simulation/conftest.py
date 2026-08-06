"""One generated dataset, shared across the statistical checks in this package.

Generating is the expensive part, and every test here asks a different question
of the same data. Building it once per session keeps the tier inside its budget
without weakening any individual check.
"""

from __future__ import annotations

import pytest
from tests.fixtures.simulation import build, short_config

from spc_platform.simulation import GeneratedDataset


@pytest.fixture(scope="session")
def dataset() -> GeneratedDataset:
    """Return the shared short-run dataset, built from the committed configuration."""
    return build(short_config())
