"""Measured average run length against published theory.

Verification by simulation per TESTING_STRATEGY.md §3.4. This is the strongest
check on the rule implementations in the suite, and it is strong for a reason
the hand-written cases cannot match: the combined in-control ARL of the four
Western Electric rules depends on every window length and every threshold at
once. Lengthen rule 4's run from eight points to nine and the figure moves by
roughly five percent — well outside the tolerance below — even though every
individual rule would still look correct in isolation.

Run counts are chosen so the standard error is a few percent of the mean, far
inside the ±15% the acceptance criteria allow, while keeping the whole module
inside the statistical tier's time budget.
"""

from __future__ import annotations

from functools import cache

import pytest

from spc_platform.analytics.rules import arl, catalogue
from spc_platform.common.errors import ConfigurationError, InsufficientDataError
from spc_platform.domain.ids import RuleId

pytestmark = pytest.mark.statistical

SEED = 20260805
"""Fixed, so a stochastic measurement is still a deterministic test."""

TOLERANCE = 0.15
"""The ±15% of theory required by TESTING_STRATEGY.md §3.4 and FR-R05."""

SHEWHART_ARL0 = 370.4
"""Reciprocal of P(|Z| > 3) = 0.0027 for the single three sigma rule.

Montgomery (2019), 8th ed., §5.3.2.
"""

WESTERN_ELECTRIC_ARL0 = 91.75
"""In-control ARL for Western Electric rules 1-4 applied together.

Montgomery (2019), 8th ed., §5.3.3, quoting Champ and Woodall (1987), whose
Table 1 gives 91.75 for the four-rule set on an individuals chart.
"""


@cache
def single_limit_rule() -> arl.ArlResult:
    """Three sigma alone, watched long enough that no run goes unresolved.

    Cached rather than held in a fixture: each measurement is shared by several
    assertions about it, and recomputing per assertion would quadruple the
    module's runtime for no additional evidence.
    """
    return arl.measure_arl([catalogue.WESTERN_ELECTRIC_1], seed=SEED, runs=8_000, max_points=4_000)


@cache
def western_electric_set() -> arl.ArlResult:
    """All four Western Electric rules together."""
    return arl.measure_arl(catalogue.WESTERN_ELECTRIC, seed=SEED, runs=8_000, max_points=1_500)


@cache
def nelson_set() -> arl.ArlResult:
    """Nelson's eight tests together."""
    return arl.measure_arl(catalogue.NELSON, seed=SEED, runs=6_000, max_points=1_500)


class TestTheSingleLimitRule:
    """Three sigma alone, whose ARL follows from the normal tail directly."""

    def test_the_measured_arl_matches_the_normal_tail(self) -> None:
        """1/0.0027 = 370.4 points between false alarms.

        Montgomery (2019), 8th ed., §5.3.2. The one figure in this module with
        a closed form, which makes it the calibration for the simulation
        machinery that the other cases rely on.
        """
        assert single_limit_rule().within(SHEWHART_ARL0, tolerance=TOLERANCE)

    def test_the_measurement_is_precise_enough_to_be_meaningful(self) -> None:
        """The standard error is small next to the tolerance being applied.

        Without this, a run count too small to resolve a 15% error would pass
        the test above by being too noisy to fail it.
        """
        assert single_limit_rule().standard_error < 0.25 * TOLERANCE * SHEWHART_ARL0

    def test_no_run_was_cut_short(self) -> None:
        """A censored run is recorded at the watch limit and biases the mean down."""
        assert single_limit_rule().censored_runs == 0

    def test_the_false_alarm_rate_is_the_reciprocal(self) -> None:
        """0.0027 signals per point, which is what the ARL is a restatement of."""
        assert single_limit_rule().false_alarm_rate == pytest.approx(0.0027, abs=3e-4)


class TestTheWesternElectricSet:
    """All four rules together, where no closed form exists."""

    def test_the_measured_arl_matches_the_published_figure(self) -> None:
        """91.75 points between false alarms for rules 1-4 together.

        Montgomery (2019), 8th ed., §5.3.3, from Champ and Woodall (1987).
        """
        assert western_electric_set().within(WESTERN_ELECTRIC_ARL0, tolerance=TOLERANCE)

    def test_the_measurement_is_precise_enough_to_be_meaningful(self) -> None:
        """The standard error is small next to the tolerance being applied."""
        assert western_electric_set().standard_error < 0.25 * TOLERANCE * WESTERN_ELECTRIC_ARL0

    def test_the_extra_rules_cost_four_times_the_false_alarms(self) -> None:
        """Adding rules 2-4 to rule 1 cuts the ARL from 370 to 92.

        The trade every fab makes without being told the price: four times as
        many investigations of processes that were behaving. Asserted here so
        that the number appears in the test suite rather than only in a
        textbook.
        """
        assert western_electric_set().mean_run_length < SHEWHART_ARL0 / 3.0

    def test_no_run_was_cut_short(self) -> None:
        """1500 points is over sixteen times the expected run length."""
        assert western_electric_set().censored_runs == 0


class TestTheNelsonSet:
    """Eight tests together, whose combined ARL is lower still."""

    def test_the_set_signals_more_often_than_western_electric(self) -> None:
        """More tests, more false alarms — the direction is not in doubt.

        No published exact figure is cited for the eight-test set, so this
        asserts the ordering and the magnitude rather than a specific value,
        and the measured figure is what gets recorded in docs/validation/.
        """
        assert nelson_set().mean_run_length < WESTERN_ELECTRIC_ARL0

    def test_the_set_is_not_so_noisy_as_to_be_unusable(self) -> None:
        """Still tens of points between false alarms, not a handful.

        A rule set that signalled every few points would be switched off within
        a week, which is the real failure mode of over-configured charts.
        """
        assert nelson_set().mean_run_length > 30.0


class TestDetectionOfARealShift:
    """Out-of-control behaviour: how fast the rules notice a process that moved."""

    def test_a_three_sigma_shift_is_caught_almost_at_once(self) -> None:
        """A shift of 3 sigma puts half the points past the limit.

        Montgomery (2019), 8th ed., §5.3.3 gives ARL_1 = 2 for a 3 sigma shift
        on a Shewhart chart with the single limit rule.
        """
        measured = arl.measure_arl(
            [catalogue.WESTERN_ELECTRIC_1],
            seed=SEED,
            runs=4_000,
            max_points=200,
            shift_sigma=3.0,
        )
        assert measured.mean_run_length == pytest.approx(2.0, rel=TOLERANCE)

    def test_the_supplementary_rules_earn_their_keep_on_a_small_shift(self) -> None:
        """At 1.5 sigma the extra rules more than halve the time to detection.

        This is the other half of the trade in ``TestTheWesternElectricSet``:
        four times the false alarms buys detection of a small sustained shift
        in a fraction of the time. Montgomery (2019), 8th ed., §5.3.3 gives
        ARL_1 near 15 for the single rule at 1.5 sigma.
        """
        alone = arl.measure_arl(
            [catalogue.WESTERN_ELECTRIC_1],
            seed=SEED,
            runs=4_000,
            max_points=500,
            shift_sigma=1.5,
        )
        together = arl.measure_arl(
            catalogue.WESTERN_ELECTRIC,
            seed=SEED,
            runs=4_000,
            max_points=500,
            shift_sigma=1.5,
        )
        assert alone.mean_run_length == pytest.approx(15.0, rel=0.2)
        assert together.mean_run_length < alone.mean_run_length / 2.0


class TestTheRefusals:
    """An ARL study that cannot be run is refused rather than approximated."""

    def test_an_empty_rule_set_is_refused(self) -> None:
        """A set with no rules never signals, and its ARL is not infinity."""
        with pytest.raises(ConfigurationError):
            arl.measure_arl([], seed=SEED)

    def test_an_unknown_rule_is_refused(self) -> None:
        """The same refusal the evaluator gives, for the same reason."""
        with pytest.raises(ConfigurationError):
            arl.measure_arl([RuleId("WE-99")], seed=SEED)

    def test_a_study_with_no_runs_is_refused(self) -> None:
        """Averaging zero run lengths has no answer worth returning."""
        with pytest.raises(InsufficientDataError):
            arl.measure_arl([catalogue.WESTERN_ELECTRIC_1], seed=SEED, runs=0)


class TestReproducibility:
    """A stochastic measurement still has to be reproducible."""

    def test_the_same_seed_gives_the_same_answer(self) -> None:
        """Otherwise a recorded ARL cannot be checked by anyone else."""
        first = arl.measure_arl(catalogue.WESTERN_ELECTRIC, seed=99, runs=500, max_points=800)
        second = arl.measure_arl(catalogue.WESTERN_ELECTRIC, seed=99, runs=500, max_points=800)
        assert first.mean_run_length == second.mean_run_length

    def test_a_different_seed_gives_a_different_answer(self) -> None:
        """Confirms the seed is actually reaching the generator."""
        first = arl.measure_arl(catalogue.WESTERN_ELECTRIC, seed=99, runs=500, max_points=800)
        second = arl.measure_arl(catalogue.WESTERN_ELECTRIC, seed=100, runs=500, max_points=800)
        assert first.mean_run_length != second.mean_run_length

    def test_the_result_records_what_it_was_measured_under(self) -> None:
        """A figure without its conditions cannot be compared to anything."""
        measured = arl.measure_arl(catalogue.WESTERN_ELECTRIC, seed=99, runs=500, max_points=800)
        assert measured.seed == 99
        assert measured.runs == 500
        assert measured.max_points == 800
        assert measured.shift_sigma == 0.0
        assert measured.rule_ids == catalogue.WESTERN_ELECTRIC
