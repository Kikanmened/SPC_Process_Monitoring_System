"""Force sample size and window beside every displayed statistic (NFR-U04)."""

from __future__ import annotations

from datetime import datetime


def format_statistic(  # noqa: PLR0913 — label fields are intentional
    name: str,
    value: float | None,
    *,
    n: int,
    window_start: datetime,
    window_end: datetime,
    estimator: str | None = None,
    unavailable_reason: str | None = None,
) -> str:
    """Return a labelled statistic line; never invent a value (NFR-U05)."""
    window = f"{window_start.isoformat()} → {window_end.isoformat()}"
    if value is None:
        reason = unavailable_reason or "not computable"
        base = f"**{name}:** unavailable ({reason})"
    else:
        base = f"**{name}:** {value:.4g}"
    extras = [f"n={n}", f"window={window}"]
    if estimator is not None:
        extras.append(f"estimator={estimator}")
    return base + " · " + " · ".join(extras)
