"""Module 1 — raw boundary: validate, quarantine, assign data_revision."""

from spc_platform.pipelines.ingest.keys import DEFAULT_MEASUREMENT_KEY, require_unique_keys
from spc_platform.pipelines.ingest.stage import IngestionResult, ingest_batch
from spc_platform.pipelines.ingest.validation import ValidationReport, validate_raw_batch

__all__ = [
    "DEFAULT_MEASUREMENT_KEY",
    "IngestionResult",
    "ValidationReport",
    "ingest_batch",
    "require_unique_keys",
    "validate_raw_batch",
]
