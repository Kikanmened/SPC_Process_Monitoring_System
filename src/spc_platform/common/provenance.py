"""Provenance: data, code, and configuration revisions on every output.

A result without all three is incomplete (FR-RP02, BO-4). Construction
requires every field — there is no partial provenance.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from spc_platform.common.time import require_aware
from spc_platform.domain.ids import CodeRevision, ConfigRevision, DataRevision


class Provenance(BaseModel):
    """The three revisions that make a result reproducible and auditable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    data_revision: DataRevision
    code_revision: CodeRevision
    config_revision: ConfigRevision
    recorded_at: datetime

    @field_validator("recorded_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return require_aware(value, field_name="recorded_at")


def capture_provenance(
    *,
    data_revision: DataRevision,
    code_revision: CodeRevision,
    config_revision: ConfigRevision,
    clock: object,
) -> Provenance:
    """Assemble provenance from the three revision identifiers and a clock.

    Parameters
    ----------
    data_revision, code_revision, config_revision
        The three revisions. None may be omitted.
    clock
        An object with a ``now() -> datetime`` method (the ``Clock`` protocol).
    """
    now = clock.now()  # type: ignore[attr-defined]
    return Provenance(
        data_revision=data_revision,
        code_revision=code_revision,
        config_revision=config_revision,
        recorded_at=now,
    )
