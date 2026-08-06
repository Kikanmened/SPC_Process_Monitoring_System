"""Stability of a measurement system over time (FR-M04).

Bias and linearity are snapshots. Stability asks whether they stay put, and it
is the only one of the three that needs a control chart rather than a hypothesis
test — because the question is not "is today's mean different from the
reference" but "is it drifting", and a t-test run monthly will keep answering
"no" all the way through a slow drift that a chart catches in four points.

This is an ordinary individuals chart applied to repeated measurement of a
check standard, which is why this module is thin: the whole point is that the
same chart machinery and the same run rules apply. What it adds is the
interpretation. A signal on a stability chart does not mean the process changed;
the part being measured has not changed at all. It means the gauge did, and
every measurement taken since the last in-control point is suspect.

References
----------
NIST/SEMATECH e-Handbook of Statistical Methods, §2.2.3 (control of the
measurement process), §2.4.
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §8.7.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from spc_platform.analytics.charts.study import ChartStudy
from spc_platform.analytics.charts.variables import (
    DEFAULT_SIGMA_MULTIPLIER,
    individuals_study,
)
from spc_platform.common.errors import ConfigurationError
from spc_platform.common.types import FloatArray

MIN_STABILITY_MEASUREMENTS = 2
"""Enough to form one moving range. A real study wants twenty or more."""


@dataclass(frozen=True, slots=True)
class StabilityResult:
    """Whether the gauge is still doing what it did when it was qualified.

    Attributes
    ----------
    study
        The I-MR study of the check standard measurements. Its limits are the
        gauge's own historical behaviour, and its rule signals are the answer.
    reference_value
        Accepted value of the check standard, if it has one. A stability study
        does not need it — drift shows as movement whatever the true value is —
        but with it the chart also detects a bias that was there from the start.
    drift
        Mean measurement minus the reference value, or ``None`` without one.
        Distinct from a bias study only in that it is computed over a window
        chosen to detect change rather than to estimate an offset.
    window_start, window_end
        Period the measurements cover.
    n_measurements
        Measurements of the check standard.
    """

    study: ChartStudy
    window_start: datetime
    window_end: datetime
    n_measurements: int
    reference_value: float | None = None
    drift: float | None = None


def stability(
    measurements: FloatArray,
    window: tuple[datetime, datetime],
    *,
    reference_value: float | None = None,
    sigma_multiplier: float = DEFAULT_SIGMA_MULTIPLIER,
) -> StabilityResult:
    """Chart repeated measurement of a check standard over time.

    The limits come from the measurements themselves, which makes this a Phase I
    study of the gauge. That is the right shape for qualification. For ongoing
    monitoring the limits should come from the qualification study and stay
    fixed, so that a gauge slowly getting worse cannot widen its own limits to
    accommodate itself — the same self-confirming failure the chart module keeps
    Phase I and Phase II apart to prevent.

    Parameters
    ----------
    measurements
        Repeated measurements of one check standard, in time order.
    window
        Start and end of the period covered, both timezone-aware.
    reference_value
        Accepted value of the standard, if known.
    sigma_multiplier
        Limit width in standard errors.

    Returns
    -------
    StabilityResult
        The I-MR study and, with a reference value, the drift from it.

    Raises
    ------
    InsufficientDataError
        If there are too few measurements to form a moving range.
    DegenerateSeriesError
        If every measurement is identical.
    ConfigurationError
        If the window is not ordered.

    References
    ----------
    NIST/SEMATECH e-Handbook, §2.2.3.
    """
    start, end = window
    if end < start:
        raise ConfigurationError(
            "a stability window ends after it starts",
            window_start=str(start),
            window_end=str(end),
        )
    study = individuals_study(measurements, sigma_multiplier=sigma_multiplier)
    drift = None if reference_value is None else float(np.mean(measurements)) - reference_value
    return StabilityResult(
        study=study,
        window_start=start,
        window_end=end,
        n_measurements=int(measurements.size),
        reference_value=reference_value,
        drift=drift,
    )
