"""Effective configuration revision hash.

Every analytical output carries this hash so a result is reproducible from
data + code + configuration revisions (FR-RP02, BO-4).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from spc_platform.domain.ids import ConfigRevision


def compute_config_revision(payload: dict[str, Any]) -> ConfigRevision:
    """Return a stable SHA-256 digest of the effective configuration payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return ConfigRevision(digest)
