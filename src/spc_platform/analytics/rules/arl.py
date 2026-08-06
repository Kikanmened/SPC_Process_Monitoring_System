"""Average run length: how often a rule set cries wolf, and how fast it notices.

Every rule added to a set buys detection with false alarms, and the exchange
rate is bad. The single three-sigma rule signals on an in-control process about
once in 370 points. Adding Western Electric's other three cuts that to about
92 — four times as many investigations of processes that were fine. Nobody
decides that deliberately; it happens when rules are switched on one at a time
because each seemed useful in isolation.

So a rule set does not ship without its measured ARL (FR-R05, FR-R06). These
functions produce it by simulation rather than by formula, because no closed
form exists for the combined sets: the rules overlap, their signals are
dependent, and the published 91.75 for the four Western Electric rules is
itself a simulation result.

References
----------
Champ, C. W. and Woodall, W. H. (1987). "Exact Results for Shewhart Control
Charts with Supplementary Runs Rules." *Technometrics* 29(4), 393-399.
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §5.3.3 and Table 5.1.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from spc_platform.analytics.rules.catalogue import CATALOGUE, Rule, RuleContext
from spc_platform.common.errors import ConfigurationError, InsufficientDataError
from spc_platform.common.types import BoolArray, FloatArray
from spc_platform.domain.ids import RuleId

DEFAULT_RUNS = 20_000
"""Independent simulated charts. Gives a standard error near 0.7% of the mean.

The run length of a Shewhart chart is close to geometric, so its standard
deviation is close to its mean and the standard error of the average is the
mean over the square root of the run count.
"""

DEFAULT_MAX_POINTS = 4_000
"""Points to watch before giving up on a run.

Ten times the in-control ARL of the loosest rule set, which leaves about two
runs in a hundred thousand unresolved. Those are reported rather than
discarded: silently dropping the long runs would bias the average downward,
which is the direction that flatters a rule set.
"""

_CHUNK_POINTS = 2_000_000
"""Points held in memory at once, so a large study does not need a large machine."""


@dataclass(frozen=True, slots=True)
class ArlResult:
    """A measured average run length with its uncertainty and its conditions.

    Attributes
    ----------
    rule_ids
        The set measured, in configured order.
    mean_run_length
        Points until the first signal, averaged over the runs.
    standard_error
        Standard error of that average. Reported because an ARL quoted without
        one invites comparison of two numbers that differ by less than their
        noise.
    runs
        Independent simulated charts.
    max_points
        Longest run watched before giving up.
    censored_runs
        Runs that reached ``max_points`` with no signal. Their run length is
        recorded as ``max_points``, so a non-zero count means the reported mean
        is an underestimate.
    shift_sigma
        Process shift the simulation ran under, in standard errors. Zero gives
        the in-control ARL_0; anything else gives the out-of-control ARL_1.
    seed
        Seed used, so the figure can be reproduced exactly.
    """

    rule_ids: tuple[RuleId, ...]
    mean_run_length: float
    standard_error: float
    runs: int
    max_points: int
    censored_runs: int
    shift_sigma: float
    seed: int

    @property
    def false_alarm_rate(self) -> float:
        """Signals per point, the reciprocal of the mean run length."""
        return 1.0 / self.mean_run_length

    def within(self, theoretical: float, *, tolerance: float) -> bool:
        """Whether the measurement agrees with a published figure.

        Parameters
        ----------
        theoretical
            Published average run length.
        tolerance
            Allowed relative deviation, e.g. 0.15 for the 15% the testing
            strategy requires.

        Returns
        -------
        bool
            True if the measured mean is within tolerance of the published one.
        """
        return abs(self.mean_run_length - theoretical) <= tolerance * theoretical


def measure_arl(
    rule_ids: Sequence[RuleId],
    *,
    seed: int,
    runs: int = DEFAULT_RUNS,
    max_points: int = DEFAULT_MAX_POINTS,
    shift_sigma: float = 0.0,
) -> ArlResult:
    """Simulate a normal process and measure how long a rule set takes to signal.

    Each run is an independent chart started fresh, watched until the first
    point any configured rule signals on. The process is standard normal about
    the centre line, shifted by ``shift_sigma`` standard errors, which is the
    model the published ARL figures assume.

    Parameters
    ----------
    rule_ids
        Rules to run together.
    seed
        Seed for the generator, making the result reproducible.
    runs
        Independent charts to simulate.
    max_points
        Points to watch before recording the run as censored.
    shift_sigma
        Sustained shift in standard errors, applied from the first point. Zero
        measures the false-alarm behaviour; 1.5 measures detection of the shift
        the acceptance criteria name.

    Returns
    -------
    ArlResult
        The measurement, its standard error, and the conditions it was made
        under.

    Raises
    ------
    ConfigurationError
        If a rule identity has no implementation.
    InsufficientDataError
        If the run count or point budget is not positive.

    References
    ----------
    Montgomery (2019), 8th ed., §5.3.3.
    """
    if runs < 1 or max_points < 1:
        raise InsufficientDataError(
            "an ARL study needs at least one run of at least one point",
            runs=runs,
            max_points=max_points,
        )
    rules = _resolve(rule_ids)
    generator = np.random.default_rng(seed)
    rows_per_chunk = max(1, _CHUNK_POINTS // max_points)

    lengths: list[FloatArray] = []
    remaining = runs
    while remaining > 0:
        rows = min(rows_per_chunk, remaining)
        series = generator.standard_normal((rows, max_points)) + shift_sigma
        lengths.append(_first_signal(series, rules, max_points))
        remaining -= rows

    observed = np.concatenate(lengths)
    mean = float(np.mean(observed))
    return ArlResult(
        rule_ids=tuple(rule_ids),
        mean_run_length=mean,
        standard_error=float(np.std(observed, ddof=1) / np.sqrt(runs)),
        runs=runs,
        max_points=max_points,
        censored_runs=int(np.count_nonzero(observed >= max_points)),
        shift_sigma=shift_sigma,
        seed=seed,
    )


def _resolve(rule_ids: Sequence[RuleId]) -> tuple[Rule, ...]:
    """Look up every configured rule, refusing an unknown identity.

    Raises
    ------
    ConfigurationError
        If a rule identity has no implementation, or none were given.
    """
    if not rule_ids:
        raise ConfigurationError("an ARL study needs at least one rule", rule_ids=())
    resolved: list[Rule] = []
    for rule_id in rule_ids:
        try:
            resolved.append(CATALOGUE[rule_id])
        except KeyError:
            raise ConfigurationError(
                "no rule with this identity is implemented",
                rule_id=rule_id,
                available=sorted(CATALOGUE),
            ) from None
    return tuple(resolved)


def _first_signal(
    series: FloatArray,
    rules: tuple[Rule, ...],
    max_points: int,
) -> FloatArray:
    """Points until the first signal in each row, or ``max_points`` if none.

    The simulated series is already in standard errors about its centre, so it
    serves as both the standardised view the limit rules read and the plotted
    values the trend rules read.
    """
    context = RuleContext(standardised=series, values=series)
    signalled: BoolArray = np.zeros(series.shape, dtype=np.bool_)
    for rule in rules:
        signalled |= rule.detect(context)

    any_signal = signalled.any(axis=-1)
    first = np.argmax(signalled, axis=-1) + 1
    lengths: FloatArray = np.where(any_signal, first, max_points).astype(np.float64)
    return lengths
