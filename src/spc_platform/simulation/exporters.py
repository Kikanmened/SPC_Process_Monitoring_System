"""Writing a dataset and its manifest, reproducibly.

The reproduction guarantee is about the *data*, not about the manifest. A
manifest records when it was written and therefore differs between runs by
design; the measurements must not. The content digest is what makes that
checkable without comparing file bytes, which would otherwise couple the
guarantee to the Parquet writer's version.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from spc_platform.simulation.generator import RAW_COLUMNS, GeneratedDataset
from spc_platform.simulation.manifests import (
    MANIFEST_FILENAME,
    MEASUREMENTS_STEM,
    DatasetManifest,
)

if TYPE_CHECKING:
    from _typeshed import ReadableBuffer

_DIGEST_BYTES = 32
_FIELD_SEPARATOR = b"\x00"

_CANONICAL_DTYPE: dict[str, str] = {
    "b": "bool",
    "i": "int64",
    "u": "int64",
    "f": "float64",
    "M": "datetime64[ns]",
}
"""Numpy kinds whose buffer may be hashed directly, and the width to hash at.

Widening first is what keeps the digest a statement about values. A slot number
stored as ``int16`` in memory and read back from CSV as ``int64`` is the same
slot, and a digest that disagreed would report a reproduction failure for a
dataset that reproduced perfectly. Every other kind — ``object`` and the pandas
string dtypes, whose numpy view is an array of *pointers* — goes through its
text form, or the digest would hash memory addresses and change on every run.
"""

_LOSSLESS_FLOAT = "%.17g"
"""Pandas' default CSV float formatting drops a unit in the last place on roughly
one value in eight. Seventeen significant digits is the shortest width that round-
trips every float64 exactly, which is what lets a CSV-loaded frame reproduce the
manifest's content digest."""


class DatasetFormat(StrEnum):
    """On-disk format for the measurement table.

    Parquet preserves dtypes and is what everything downstream reads. CSV exists
    because the raw zone boundary is CSV in the reference design
    (modules/01-data-ingestion.md), and ingestion must be exercised against the
    format it will actually receive.
    """

    PARQUET = "parquet"
    CSV = "csv"

    @property
    def suffix(self) -> str:
        """File extension for this format."""
        return f".{self.value}"


@dataclass(frozen=True, slots=True)
class DatasetPaths:
    """Where a written dataset lives."""

    directory: Path
    measurements: Path
    manifest: Path


def content_digest(frame: pd.DataFrame) -> str:
    """Return a stable digest of a measurement frame's contents.

    Hashes the column buffers in the fixed raw-zone order, so the digest depends
    on the values and their order and on nothing else — not on the file format,
    the compression codec, or the library version that wrote it.
    """
    digest = hashlib.blake2b(digest_size=_DIGEST_BYTES)
    for column in RAW_COLUMNS:
        digest.update(column.encode("utf-8"))
        digest.update(_FIELD_SEPARATOR)
        _update_with_series(digest, frame[column])
        digest.update(_FIELD_SEPARATOR)
    return digest.hexdigest()


class _Digest(Protocol):
    """The one method this module needs from a hash object.

    Narrower than ``hashlib._Hash``, which is private and does not admit the
    concrete ``blake2b`` type anyway.
    """

    def update(self, data: ReadableBuffer, /) -> None: ...


def _update_with_series(digest: _Digest, series: pd.Series[Any]) -> None:
    """Feed one column into ``digest``.

    Only fixed-width numeric and datetime buffers may be hashed as raw bytes.
    Everything else — ``object``, and the pandas string dtypes, whose numpy view
    is an array of *pointers* — has to go through its text form, or the digest
    ends up hashing memory addresses and changes on every run.
    """
    values = series.to_numpy()
    canonical = _CANONICAL_DTYPE.get(values.dtype.kind)
    if canonical is not None:
        digest.update(np.ascontiguousarray(values.astype(canonical)).tobytes())
        return
    digest.update(_FIELD_SEPARATOR.join(str(value).encode("utf-8") for value in series))


def _write_measurements(frame: pd.DataFrame, path: Path, dataset_format: DatasetFormat) -> None:
    if dataset_format is DatasetFormat.PARQUET:
        table = pa.Table.from_pandas(frame, preserve_index=False)
        pq.write_table(table, path, compression="zstd", version="2.6")
        return
    frame.to_csv(
        path,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%S%z",
        float_format=_LOSSLESS_FLOAT,
    )


def write_dataset(
    dataset: GeneratedDataset,
    root: Path,
    *,
    dataset_format: DatasetFormat = DatasetFormat.PARQUET,
) -> tuple[DatasetPaths, DatasetManifest]:
    """Write measurements and manifest under ``root/<dataset_id>/``.

    Parameters
    ----------
    dataset
        The generated frame and its manifest.
    root
        Root of the synthetic zone, normally ``data/synthetic/``.
    dataset_format
        Format for the measurement table.

    Returns
    -------
    tuple
        The paths written, and the manifest as written — which carries the
        content digest that the generated manifest could not know until the
        frame was final.
    """
    directory = root / dataset.manifest.dataset_id
    directory.mkdir(parents=True, exist_ok=True)

    measurements = directory / f"{MEASUREMENTS_STEM}{dataset_format.suffix}"
    manifest_path = directory / MANIFEST_FILENAME

    _write_measurements(dataset.frame, measurements, dataset_format)
    manifest = dataset.manifest.model_copy(update={"content_digest": content_digest(dataset.frame)})
    manifest_path.write_text(manifest.to_json(), encoding="utf-8")

    return (
        DatasetPaths(directory=directory, measurements=measurements, manifest=manifest_path),
        manifest,
    )


def read_measurements(path: Path) -> pd.DataFrame:
    """Read a written measurement table back, restoring dtypes.

    Parameters
    ----------
    path
        Path to ``measurements.parquet`` or ``measurements.csv``.
    """
    frame: pd.DataFrame
    if path.suffix == DatasetFormat.PARQUET.suffix:
        frame = pq.read_table(path).to_pandas()
    else:
        # Pandas' default CSV float parser trades exactness for speed and lands a
        # unit in the last place away on a fifth of the values. Only the
        # round-trip parser inverts what the writer emitted.
        frame = pd.read_csv(path, float_precision="round_trip")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, format="mixed")
    return frame.loc[:, list(RAW_COLUMNS)]
