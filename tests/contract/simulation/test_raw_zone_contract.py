"""The generator emits what the pipeline agreed to accept.

Two packages that never import each other still have to agree on a table. The
generator is a leaf the platform cannot see (ADR-0021), which is what keeps the
benchmark honest, but it also means a rename on either side compiles cleanly and
type-checks cleanly and is caught by nothing. This is the contract that catches
it, and it is deliberately owned by neither: the schema comes from the pipeline,
the frame comes from the generator, and the test asserts they meet.

Checked at the raw zone because that is the boundary the dataset is delivered
at. What the pipeline does afterwards is the pipeline's business.
"""

from __future__ import annotations

import pandas as pd
import pytest
from tests.fixtures.simulation import build, short_config

from spc_platform.pipelines.schemas.measurement import RawMeasurementSchema
from spc_platform.simulation import RAW_COLUMNS

pytestmark = pytest.mark.contract

CONTRACT_LOTS = 40
"""Short. A schema violation is structural and shows up in the first lots."""


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    """Return the measurement table from a short generated run."""
    return build(short_config(lots=CONTRACT_LOTS)).frame


def test_the_generated_frame_satisfies_the_raw_measurement_schema(frame: pd.DataFrame) -> None:
    """Every column, dtype, nullability, and range the ingestion zone requires.

    ``lazy`` so a mismatch reports all of its failures at once; the first one
    alone rarely says whether the schema moved or the generator did.
    """
    RawMeasurementSchema.validate(frame, lazy=True)


def test_the_generator_and_the_schema_name_the_same_columns(frame: pd.DataFrame) -> None:
    """The schema is strict, so an extra column already fails above.

    This pins the other direction: a column added to the schema and not to the generator would
    leave every generated dataset unloadable.
    """
    assert set(RAW_COLUMNS) == set(RawMeasurementSchema.columns)
    assert list(frame.columns) == list(RAW_COLUMNS)


def test_no_measurement_is_pre_labelled_as_suspect(frame: pd.DataFrame) -> None:
    """The schema permits ``suspect``; the generator must never use it.

    Deciding that a point is suspect is a disposition the platform makes, and a dataset that
    arrived with the answers would score itself (DATASET_GUIDE.md §5).
    """
    assert set(frame["measurement_status"]) <= {"valid", "superseded"}
