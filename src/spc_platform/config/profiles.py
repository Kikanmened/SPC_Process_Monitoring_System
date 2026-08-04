"""Deployment profiles selecting the environment overlay."""

from __future__ import annotations

from enum import StrEnum


class Profile(StrEnum):
    """Supported runtime profiles (SYSTEM_ARCHITECTURE.md §6)."""

    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"
