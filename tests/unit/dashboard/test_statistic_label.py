"""Statistic labels always carry n and window."""

from __future__ import annotations

from datetime import UTC, datetime

from dashboard.components.statistic_label import format_statistic


def test_format_statistic_includes_n_and_window() -> None:
    text = format_statistic(
        "Cpk",
        1.33,
        n=42,
        window_start=datetime(2025, 7, 1, tzinfo=UTC),
        window_end=datetime(2025, 7, 14, tzinfo=UTC),
        estimator="mr_bar_d2",
    )
    assert "n=42" in text
    assert "window=" in text
    assert "1.33" in text


def test_format_statistic_states_unavailable() -> None:
    text = format_statistic(
        "Cpk",
        None,
        n=0,
        window_start=datetime(2025, 7, 1, tzinfo=UTC),
        window_end=datetime(2025, 7, 14, tzinfo=UTC),
        unavailable_reason="process out of control",
    )
    assert "unavailable" in text
    assert "process out of control" in text
