"""The patterns every run rule is built from, vectorised over the whole series.

Both published rule sets are combinations of five ideas: a point too far out, k
of the last m too far out on one side, a run on one side of the centre, a
monotone run, and a run confined to or excluded from the middle. Writing those
five once means the Western Electric and Nelson sets are declarations rather
than implementations, and an off-by-one has one place to hide instead of
twelve.

Two conventions apply throughout and are worth stating because published
descriptions leave them implicit.

**Where a signal is reported.** A rule needing m points signals on the last
point of the window that satisfies it. Reporting it at the start would place
the alarm before the evidence existed, and an operator investigating a
three-hours-ago timestamp for a pattern that only just completed is being sent
to the wrong shift.

**What a tie does.** A point exactly on the centre line belongs to neither side
and breaks a run; two consecutive equal values are not an increase and break a
trend. Both follow from the rules being about the process moving, and both are
reachable with the quantised values real metrology returns.

Every function here works along the last axis, so a two-dimensional input is
treated as a batch of independent series. That is not generality for its own
sake: measuring an average run length means evaluating the same rules over
thousands of simulated series, and doing it one series at a time is the
difference between a second and a quarter of an hour.
"""

from __future__ import annotations

import numpy as np

from spc_platform.common.types import BoolArray, FloatArray

MIN_RULE_WINDOW = 1
"""A rule looks at at least one point."""


def _empty_signal(like: FloatArray | BoolArray) -> BoolArray:
    """No point signalled anywhere, shaped like the input series."""
    signal: BoolArray = np.zeros(like.shape, dtype=np.bool_)
    return signal


def _windows(flags: BoolArray, window: int) -> BoolArray:
    """Every consecutive run of ``window`` flags, along the last axis."""
    view: BoolArray = np.lib.stride_tricks.sliding_window_view(flags, window, axis=-1)
    return view


def _signal_at_window_end(
    matched: BoolArray,
    window: int,
    like: FloatArray,
) -> BoolArray:
    """Place a per-window result on the last point of each window."""
    signal = _empty_signal(like)
    if matched.size:
        signal[..., window - 1 :] = matched
    return signal


def beyond(standardised: FloatArray, threshold: float) -> BoolArray:
    """Points further than ``threshold`` standard errors from the centre, either side.

    Parameters
    ----------
    standardised
        Plotted points as distances from the centre line, in standard errors.
    threshold
        Distance in standard errors, positive.

    Returns
    -------
    BoolArray
        One flag per point.
    """
    flagged: BoolArray = np.abs(standardised) > threshold
    return flagged


def k_of_m_beyond(
    standardised: FloatArray,
    *,
    k: int,
    m: int,
    threshold: float,
) -> BoolArray:
    """At least ``k`` of the last ``m`` points beyond ``threshold`` on the same side.

    The same-side requirement is the whole point of the rule and the most
    common thing to get wrong. Two points straddling the centre line, one high
    and one low, are evidence of spread, not of a shift, and a rule that
    counted them together would fire on exactly the pattern it is meant to
    ignore.

    Parameters
    ----------
    standardised
        Plotted points in standard errors from the centre.
    k
        How many of the window must be beyond the threshold.
    m
        Window length in points.
    threshold
        Distance in standard errors.

    Returns
    -------
    BoolArray
        One flag per point, set on the last point of each matching window.
    """
    if standardised.shape[-1] < m:
        return _empty_signal(standardised)
    above = _windows(standardised > threshold, m).sum(axis=-1) >= k
    below = _windows(standardised < -threshold, m).sum(axis=-1) >= k
    return _signal_at_window_end(above | below, m, standardised)


def run_on_one_side(standardised: FloatArray, *, length: int) -> BoolArray:
    """``length`` consecutive points on the same side of the centre line.

    Parameters
    ----------
    standardised
        Plotted points in standard errors from the centre.
    length
        Run length in points.

    Returns
    -------
    BoolArray
        One flag per point, set on the last point of each matching run.
    """
    if standardised.shape[-1] < length:
        return _empty_signal(standardised)
    above = _windows(standardised > 0.0, length).all(axis=-1)
    below = _windows(standardised < 0.0, length).all(axis=-1)
    return _signal_at_window_end(above | below, length, standardised)


def monotonic_run(values: FloatArray, *, length: int) -> BoolArray:
    """``length`` consecutive points all increasing or all decreasing.

    Counted in points, not steps: a run of six points is five consecutive
    increases. Published descriptions say "six points in a row steadily
    increasing", and reading that as six increases makes the rule fire about
    half as often as its documented false-alarm rate.

    Parameters
    ----------
    values
        The plotted statistic. Not standardised — a trend is a trend in the
        original units, and standardising by a per-point standard error could
        introduce or remove one where limits vary.
    length
        Run length in points.

    Returns
    -------
    BoolArray
        One flag per point, set on the last point of each matching run.
    """
    if values.shape[-1] < length:
        return _empty_signal(values)
    steps = length - 1
    differences = np.diff(values, axis=-1)
    rising = _windows(differences > 0.0, steps).all(axis=-1)
    falling = _windows(differences < 0.0, steps).all(axis=-1)
    return _signal_at_window_end(rising | falling, length, values)


def alternating_run(values: FloatArray, *, length: int) -> BoolArray:
    """``length`` consecutive points alternating up and down.

    A sawtooth is the signature of two interleaved populations — alternate
    heads on a two-head tool, or an odd-even effect in a sequence — which a
    limit-based rule cannot see because every point stays comfortably inside.

    Parameters
    ----------
    values
        The plotted statistic, in its own units.
    length
        Run length in points.

    Returns
    -------
    BoolArray
        One flag per point, set on the last point of each matching run.
    """
    if values.shape[-1] < length:
        return _empty_signal(values)
    directions = np.sign(np.diff(values, axis=-1))
    reversals = (directions[..., 1:] * directions[..., :-1]) < 0.0
    return _signal_at_window_end(_windows(reversals, length - 2).all(axis=-1), length, values)


def run_within(standardised: FloatArray, *, length: int, threshold: float) -> BoolArray:
    """``length`` consecutive points all inside ``threshold`` standard errors.

    Hugging the centre line is not good news. It usually means the limits are
    too wide for the process as it now runs — a stale baseline, or data that
    has been averaged before charting — and a chart that cannot signal is worse
    than no chart, because it is trusted.

    Parameters
    ----------
    standardised
        Plotted points in standard errors from the centre.
    length
        Run length in points.
    threshold
        Distance in standard errors that defines "inside".

    Returns
    -------
    BoolArray
        One flag per point, set on the last point of each matching run.
    """
    if standardised.shape[-1] < length:
        return _empty_signal(standardised)
    inside = np.abs(standardised) < threshold
    return _signal_at_window_end(_windows(inside, length).all(axis=-1), length, standardised)


def run_outside_straddling(
    standardised: FloatArray,
    *,
    length: int,
    threshold: float,
) -> BoolArray:
    """``length`` consecutive points beyond ``threshold``, appearing on both sides.

    Nelson's mixture rule. The both-sides requirement is part of the published
    definition and is what separates it from a sustained shift: points far from
    the centre on alternating sides indicate two populations being sampled, not
    one population that has moved.

    Parameters
    ----------
    standardised
        Plotted points in standard errors from the centre.
    length
        Run length in points.
    threshold
        Distance in standard errors that defines "outside".

    Returns
    -------
    BoolArray
        One flag per point, set on the last point of each matching run.

    References
    ----------
    Nelson, L. S. (1984). "The Shewhart Control Chart — Tests for Special
    Causes." *Journal of Quality Technology* 16(4), 237-239, test 8.
    """
    if standardised.shape[-1] < length:
        return _empty_signal(standardised)
    outside = _windows(np.abs(standardised) > threshold, length).all(axis=-1)
    has_high = _windows(standardised > threshold, length).any(axis=-1)
    has_low = _windows(standardised < -threshold, length).any(axis=-1)
    return _signal_at_window_end(outside & has_high & has_low, length, standardised)
