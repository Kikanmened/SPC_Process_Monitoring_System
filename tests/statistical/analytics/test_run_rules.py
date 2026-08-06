"""Run rules against hand-constructed series where the answer is countable.

No textbook tabulates "which point does rule 3 fire on", so these are
hand-computed cases per TESTING_STRATEGY.md §3.2: each series is short enough
to read, and the docstring states the expected signal and why. The published
authority for the rules themselves is the wording in
``analytics/rules/catalogue.py``; what is checked here is that the
implementation matches that wording point for point.

The properties that must hold for *every* series — sign symmetry, the effect of
window length — are in ``test_rule_invariants.py``. The false alarm rate the
whole set produces is in ``test_arl.py``, and that is the check that would
catch a window off by one even if every case below were written to match the
same mistake.
"""

from __future__ import annotations

import numpy as np
import pytest

from spc_platform.analytics.rules import catalogue, evaluate
from spc_platform.common.errors import ConfigurationError
from spc_platform.domain.ids import RuleId

from .conftest import PanelFactory, alternating, rule_set_of

pytestmark = pytest.mark.statistical


def _signalled_points(
    rule_id: RuleId,
    panel_factory: PanelFactory,
    values: list[float],
) -> list[int]:
    """Point indices one rule signals on."""
    violations = evaluate.evaluate_panel(rule_set_of(rule_id), panel_factory(values))
    return [violation.point_index for violation in violations]


class TestWesternElectricRuleOne:
    """One point beyond three sigma."""

    def test_a_point_past_the_limit_signals(self, standard_panel: PanelFactory) -> None:
        """Point 2 is at 3.4 sigma; the others are inside."""
        points = _signalled_points(
            catalogue.WESTERN_ELECTRIC_1, standard_panel, [0.5, -1.0, 3.4, 0.2]
        )
        assert points == [2]

    def test_a_point_exactly_on_the_limit_does_not_signal(
        self, standard_panel: PanelFactory
    ) -> None:
        """The rule is "beyond" the limit, not "at or beyond" it.

        A point exactly on the control limit is the boundary case the wording
        settles: Western Electric's rule is a point outside zone A, and a point
        on the line is on the edge of zone A rather than past it.
        """
        assert _signalled_points(catalogue.WESTERN_ELECTRIC_1, standard_panel, [3.0, -3.0]) == []

    def test_the_rule_is_symmetric(self, standard_panel: PanelFactory) -> None:
        """A point 3.4 sigma below the centre signals exactly as one above does."""
        assert _signalled_points(
            catalogue.WESTERN_ELECTRIC_1, standard_panel, [0.5, -1.0, -3.4, 0.2]
        ) == [2]


class TestWesternElectricRuleTwo:
    """Two of three consecutive points beyond two sigma, same side."""

    def test_two_of_three_on_one_side_signals_at_the_third(
        self, standard_panel: PanelFactory
    ) -> None:
        """Points 1 and 3 are past 2 sigma high, so the window 1-3 matches.

        The signal lands on point 3, the last of the window: that is the first
        moment the pattern is complete and visible.
        """
        values = [0.0, 2.5, 0.1, 2.6, 0.0]
        assert _signalled_points(catalogue.WESTERN_ELECTRIC_2, standard_panel, values) == [3]

    def test_points_on_opposite_sides_do_not_signal(self, standard_panel: PanelFactory) -> None:
        """One point high and one low is spread, not a shift.

        This is the case a naive implementation gets wrong by testing
        ``abs(z) > 2`` and counting both. Doing so turns the rule into a
        detector for the very pattern it is designed to ignore.
        """
        values = [0.0, 2.5, 0.1, -2.6, 0.0]
        assert _signalled_points(catalogue.WESTERN_ELECTRIC_2, standard_panel, values) == []

    def test_one_point_beyond_two_sigma_is_not_enough(self, standard_panel: PanelFactory) -> None:
        """A single excursion into zone B is expected roughly once in 22 points."""
        assert (
            _signalled_points(catalogue.WESTERN_ELECTRIC_2, standard_panel, [0.0, 2.5, 0.1, 0.4])
            == []
        )

    def test_three_in_a_row_signals_on_every_window_that_qualifies(
        self, standard_panel: PanelFactory
    ) -> None:
        """Points 0-2 are all beyond 2 sigma, and point 3 sits back at the centre.

        Two windows qualify. The one ending at point 2 holds three qualifying
        points; the one ending at point 3 still holds two of them, which is the
        threshold. So the rule signals at 2 and again at 3, and the process is
        flagged until the pattern has fully aged out of the window rather than
        only at the moment it appeared.
        """
        values = [2.1, 2.2, 2.3, 0.0]
        assert _signalled_points(catalogue.WESTERN_ELECTRIC_2, standard_panel, values) == [
            2,
            3,
        ]


class TestWesternElectricRuleThree:
    """Four of five consecutive points beyond one sigma, same side."""

    def test_four_of_five_signals_at_the_fifth(self, standard_panel: PanelFactory) -> None:
        """Points 0, 1, 3, 4 are past 1 sigma high; point 2 is not.

        Four of the five-point window 0-4 qualify, so the signal is at point 4.
        """
        values = [1.2, 1.3, 0.1, 1.4, 1.5]
        assert _signalled_points(catalogue.WESTERN_ELECTRIC_3, standard_panel, values) == [4]

    def test_three_of_five_does_not_signal(self, standard_panel: PanelFactory) -> None:
        """One short of the threshold is not a near miss; it is a pass."""
        values = [1.2, 1.3, 0.1, 0.2, 1.5]
        assert _signalled_points(catalogue.WESTERN_ELECTRIC_3, standard_panel, values) == []

    def test_four_of_five_split_across_the_centre_does_not_signal(
        self, standard_panel: PanelFactory
    ) -> None:
        """Two high and two low is not four on one side."""
        values = [1.2, 1.3, 0.1, -1.4, -1.5]
        assert _signalled_points(catalogue.WESTERN_ELECTRIC_3, standard_panel, values) == []


class TestWesternElectricRuleFour:
    """Eight consecutive points on one side of the centre line."""

    def test_eight_on_one_side_signals_at_the_eighth(self, standard_panel: PanelFactory) -> None:
        """Eight small positive values, none anywhere near a limit.

        This is the rule that catches a sustained shift too small to breach a
        three sigma limit — the situation where a chart with rule 1 alone will
        run for hundreds of points without comment.
        """
        values = [0.2] * 8
        assert _signalled_points(catalogue.WESTERN_ELECTRIC_4, standard_panel, values) == [7]

    def test_seven_on_one_side_does_not_signal(self, standard_panel: PanelFactory) -> None:
        """Seven is the longest run the rule tolerates."""
        assert _signalled_points(catalogue.WESTERN_ELECTRIC_4, standard_panel, [0.2] * 7) == []

    def test_a_point_on_the_centre_line_breaks_the_run(self, standard_panel: PanelFactory) -> None:
        """A value exactly at the centre is on neither side.

        Reachable in practice: metrology returns quantised values, and a
        parameter whose centre line falls on a representable value will produce
        exact ties.
        """
        values = [0.2, 0.2, 0.2, 0.0, 0.2, 0.2, 0.2, 0.2]
        assert _signalled_points(catalogue.WESTERN_ELECTRIC_4, standard_panel, values) == []

    def test_a_longer_run_signals_on_every_completed_window(
        self, standard_panel: PanelFactory
    ) -> None:
        """Ten points on one side complete windows ending at 7, 8, and 9."""
        assert _signalled_points(catalogue.WESTERN_ELECTRIC_4, standard_panel, [0.2] * 10) == [
            7,
            8,
            9,
        ]


class TestNelsonTrendRule:
    """Six consecutive points steadily increasing or decreasing."""

    def test_six_rising_points_signal_at_the_sixth(self, standard_panel: PanelFactory) -> None:
        """Six points is five increases, and the signal lands on the sixth.

        Reading "six points steadily increasing" as six increases would need
        seven points and halves the rule's sensitivity.
        """
        values = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
        assert _signalled_points(catalogue.NELSON_3, standard_panel, values) == [5]

    def test_five_rising_points_do_not_signal(self, standard_panel: PanelFactory) -> None:
        """One point short of the window."""
        assert (
            _signalled_points(catalogue.NELSON_3, standard_panel, [0.0, 0.1, 0.2, 0.3, 0.4]) == []
        )

    def test_a_repeated_value_breaks_the_trend(self, standard_panel: PanelFactory) -> None:
        """Equal consecutive values are not an increase.

        Quantised metrology produces ties routinely, and treating them as
        continuations would make the trend rule fire on a flat process that
        happens to drift by less than one measurement resolution.
        """
        values = [0.0, 0.1, 0.2, 0.2, 0.3, 0.4]
        assert _signalled_points(catalogue.NELSON_3, standard_panel, values) == []

    def test_a_falling_run_signals_too(self, standard_panel: PanelFactory) -> None:
        """The rule is direction-agnostic."""
        values = [0.5, 0.4, 0.3, 0.2, 0.1, 0.0]
        assert _signalled_points(catalogue.NELSON_3, standard_panel, values) == [5]


class TestNelsonAlternatingRule:
    """Fourteen consecutive points alternating up and down."""

    def test_fourteen_alternating_points_signal_at_the_fourteenth(
        self, standard_panel: PanelFactory
    ) -> None:
        """A pure sawtooth of fourteen points, all well inside the limits.

        The pattern of two interleaved populations — alternate heads, odd and
        even slots — which no limit-based rule can see.
        """
        values = list(alternating(14))
        assert _signalled_points(catalogue.NELSON_4, standard_panel, values) == [13]

    def test_thirteen_alternating_points_do_not_signal(self, standard_panel: PanelFactory) -> None:
        """One short of the window."""
        assert _signalled_points(catalogue.NELSON_4, standard_panel, list(alternating(13))) == []

    def test_one_missed_beat_breaks_the_pattern(self, standard_panel: PanelFactory) -> None:
        """Two consecutive rises in the middle end the alternation."""
        values = list(alternating(14))
        values[7] = values[6] + 0.1
        assert _signalled_points(catalogue.NELSON_4, standard_panel, values) == []


class TestNelsonHuggingRule:
    """Fifteen consecutive points within one sigma."""

    def test_fifteen_points_near_the_centre_signal(self, standard_panel: PanelFactory) -> None:
        """Limits too wide for the process are as dangerous as limits too tight.

        A chart that cannot signal still gets read, and gets believed.
        """
        values = list(alternating(15, amplitude=0.2))
        assert _signalled_points(catalogue.NELSON_7, standard_panel, values) == [14]

    def test_one_excursion_past_one_sigma_breaks_the_run(
        self, standard_panel: PanelFactory
    ) -> None:
        """A single point in zone B or beyond resets the count."""
        values = list(alternating(15, amplitude=0.2))
        values[7] = 1.4
        assert _signalled_points(catalogue.NELSON_7, standard_panel, values) == []


class TestNelsonMixtureRule:
    """Eight consecutive points beyond one sigma, appearing on both sides."""

    def test_eight_straddling_points_signal(self, standard_panel: PanelFactory) -> None:
        """Alternating between the two outer zones, never near the centre.

        Two populations being sampled alternately: a lot running on two
        chambers, charted as though it ran on one.
        """
        values = [1.5, -1.5, 1.6, -1.6, 1.5, -1.5, 1.4, -1.4]
        assert _signalled_points(catalogue.NELSON_8, standard_panel, values) == [7]

    def test_eight_on_one_side_does_not_signal_the_mixture_rule(
        self, standard_panel: PanelFactory
    ) -> None:
        """A sustained shift is not a mixture, and rule 2 is what catches it.

        The both-sides requirement is what separates the two, and an
        implementation that drops it turns rule 8 into a duplicate of a rule
        that already exists with a longer window.
        """
        values = [1.5] * 8
        assert _signalled_points(catalogue.NELSON_8, standard_panel, values) == []

    def test_a_point_inside_one_sigma_breaks_the_run(self, standard_panel: PanelFactory) -> None:
        """The rule requires none of the eight to be in zone C."""
        values = [1.5, -1.5, 0.4, -1.6, 1.5, -1.5, 1.4, -1.4]
        assert _signalled_points(catalogue.NELSON_8, standard_panel, values) == []


class TestNelsonRunRule:
    """Nine consecutive points on one side — Western Electric's rule 4 lengthened."""

    def test_nine_on_one_side_signals(self, standard_panel: PanelFactory) -> None:
        """Nelson's test 2 needs nine where Western Electric's rule 4 needs eight."""
        assert _signalled_points(catalogue.NELSON_2, standard_panel, [0.2] * 9) == [8]

    def test_eight_on_one_side_does_not(self, standard_panel: PanelFactory) -> None:
        """The one point of difference between the two published sets."""
        assert _signalled_points(catalogue.NELSON_2, standard_panel, [0.2] * 8) == []


class TestTheEvaluationItself:
    """How violations are recorded, independent of which rule found them."""

    def test_every_violation_carries_its_rule_and_severity(
        self, standard_panel: PanelFactory
    ) -> None:
        """Rule identity and severity are what make a violation actionable."""
        rule_set = rule_set_of(catalogue.WESTERN_ELECTRIC_1)
        violations = evaluate.evaluate_panel(rule_set, standard_panel([0.0, 4.0]))
        assert len(violations) == 1
        assert violations[0].rule_id == catalogue.WESTERN_ELECTRIC_1
        assert violations[0].severity is rule_set.rules[0].severity
        assert violations[0].statistic_value == pytest.approx(4.0)

    def test_a_violation_carries_the_timestamp_of_its_point(
        self, standard_panel: PanelFactory
    ) -> None:
        """An index is not something an engineer can act on; a time is."""
        panel = standard_panel([0.0, 0.0, 4.0])
        violations = evaluate.evaluate_panel(rule_set_of(catalogue.WESTERN_ELECTRIC_1), panel)
        assert violations[0].timestamp == panel.series.timestamps[2]

    def test_several_rules_firing_on_one_point_give_several_violations(
        self, standard_panel: PanelFactory
    ) -> None:
        """Collapsing them would discard the reason, which is the actionable part."""
        values = [2.5, 2.6, 4.0]
        rule_set = rule_set_of(
            catalogue.WESTERN_ELECTRIC_1,
            catalogue.WESTERN_ELECTRIC_2,
            catalogue.WESTERN_ELECTRIC_3,
        )
        violations = evaluate.evaluate_panel(rule_set, standard_panel(values))
        rules_at_last_point = {
            violation.rule_id for violation in violations if violation.point_index == 2
        }
        assert rules_at_last_point == {
            catalogue.WESTERN_ELECTRIC_1,
            catalogue.WESTERN_ELECTRIC_2,
        }

    def test_violations_come_back_in_point_order(self, standard_panel: PanelFactory) -> None:
        """Ordering is deterministic so runs can be compared to each other."""
        values = [4.0, 0.0, -4.0, 0.0, 4.0]
        violations = evaluate.evaluate_panel(
            rule_set_of(catalogue.WESTERN_ELECTRIC_1), standard_panel(values)
        )
        indices = [violation.point_index for violation in violations]
        assert indices == sorted(indices)

    def test_an_unknown_rule_is_refused(self, standard_panel: PanelFactory) -> None:
        """A configuration naming a rule that does not exist must not run silently."""
        with pytest.raises(ConfigurationError):
            evaluate.evaluate_panel(rule_set_of(RuleId("WE-99")), standard_panel([0.0, 1.0]))

    def test_rules_needing_more_history_are_named(self) -> None:
        """A dormant rule is not a passing rule, and the difference must be visible.

        On a twelve-point series from a new tool, Nelson's tests 4 and 7 have
        not run at all. A chart that reports "no violations" without saying so
        is describing a test it never performed.
        """
        rule_set = rule_set_of(catalogue.NELSON_1, catalogue.NELSON_4, catalogue.NELSON_7)
        dormant = evaluate.insufficient_history(rule_set, points=12)
        assert dormant == (catalogue.NELSON_4, catalogue.NELSON_7)

    def test_no_rule_is_dormant_on_a_long_series(self) -> None:
        """Every published rule has run by twenty points."""
        rule_set = rule_set_of(*catalogue.NELSON, *catalogue.WESTERN_ELECTRIC)
        assert evaluate.insufficient_history(rule_set, points=20) == ()


class TestTheZoneBoundaries:
    """Rules read zones, and the zones are where the published wording puts them."""

    def test_the_zones_are_at_one_two_and_three_sigma(self) -> None:
        """Western Electric's zones C, B, and A, in standard errors."""
        assert (catalogue.ZONE_C, catalogue.ZONE_B, catalogue.ZONE_A) == (1.0, 2.0, 3.0)

    def test_every_catalogued_rule_is_reachable_by_its_identity(self) -> None:
        """Configuration refers to rules by string; nothing may be unreachable."""
        for rule_id, rule in catalogue.CATALOGUE.items():
            assert rule.rule_id == rule_id

    def test_the_two_published_sets_are_complete(self) -> None:
        """Four Western Electric rules and eight Nelson tests, all catalogued."""
        assert len(catalogue.WESTERN_ELECTRIC) == 4
        assert len(catalogue.NELSON) == 8
        assert set(catalogue.WESTERN_ELECTRIC) <= set(catalogue.CATALOGUE)
        assert set(catalogue.NELSON) <= set(catalogue.CATALOGUE)

    def test_the_shared_rules_behave_identically(self, standard_panel: PanelFactory) -> None:
        """Nelson's tests 1, 5, and 6 are Western Electric's rules 1, 2, and 3.

        Recorded under both identities because a fab configures one set or the
        other and expects its own numbering in the violation record, but they
        must not be allowed to drift apart.
        """
        generator = np.random.default_rng(20260805)
        values = list(generator.normal(0.0, 1.0, 200))
        panel = standard_panel(values)
        for western, nelson in (
            (catalogue.WESTERN_ELECTRIC_1, catalogue.NELSON_1),
            (catalogue.WESTERN_ELECTRIC_2, catalogue.NELSON_5),
            (catalogue.WESTERN_ELECTRIC_3, catalogue.NELSON_6),
        ):
            west_points = [
                violation.point_index
                for violation in evaluate.evaluate_panel(rule_set_of(western), panel)
            ]
            nelson_points = [
                violation.point_index
                for violation in evaluate.evaluate_panel(rule_set_of(nelson), panel)
            ]
            assert west_points == nelson_points
