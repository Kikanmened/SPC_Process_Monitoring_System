"""Shared pytest configuration.

Test tiers are directories (TESTING_STRATEGY.md §2). The corresponding marker
is applied here from the directory rather than written on each test, because a
marker that has to be remembered is a marker that will be forgotten — and an
unmarked test silently escapes every ``-m`` selection the quality gates use,
which means it runs nowhere and defends nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).parent

TIERS = frozenset(
    {
        "unit",
        "statistical",
        "integration",
        "contract",
        "e2e",
        "performance",
    }
)

# Directories under tests/ that hold support code rather than a tier.
SUPPORT_DIRECTORIES = frozenset({"fixtures", "factories"})


def pytest_collection_modifyitems(
    config: pytest.Config,  # noqa: ARG001
    items: list[pytest.Item],
) -> None:
    """Apply each test's tier marker, and refuse tests that sit outside a tier."""
    misplaced: list[str] = []

    for item in items:
        relative = Path(str(item.path)).relative_to(TESTS_ROOT)
        tier = relative.parts[0] if len(relative.parts) > 1 else ""
        if tier in TIERS:
            item.add_marker(getattr(pytest.mark, tier))
        elif tier not in SUPPORT_DIRECTORIES:
            misplaced.append(str(relative))

    if misplaced:
        listed = "\n  ".join(sorted(set(misplaced)))
        message = (
            "Every test belongs to a tier directory "
            f"({', '.join(sorted(TIERS))}). These do not:\n  {listed}"
        )
        raise pytest.UsageError(message)
