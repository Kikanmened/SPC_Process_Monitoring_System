"""The published rule sets, declared in terms of the shared primitives.

Two sets ship with the platform. Western Electric's four rules are the ones
most fabs run and the ones Montgomery tabulates an in-control average run
length for. Nelson's eight extend them with pattern tests — trend, sawtooth,
hugging, and mixture — that a limit-based rule cannot see.

They overlap: Nelson tests 1, 5, and 6 are Western Electric rules 1, 2, and 3.
Nelson test 2 is Western Electric rule 4 lengthened from eight points to nine.
That overlap is why a rule set is a configured list rather than a fixed
bundle — running both sets together roughly doubles the false alarm rate while
adding almost no new detection, and the ARL measurement in
``analytics/rules/arl.py`` is what makes the trade visible rather than
theoretical.

References
----------
Western Electric Company (1956). *Statistical Quality Control Handbook*,
2nd ed., pp. 25-28.
Nelson, L. S. (1984). "The Shewhart Control Chart — Tests for Special Causes."
*Journal of Quality Technology* 16(4), 237-239.
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §5.3.2 and Table 5.1.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType

from spc_platform.analytics.rules import primitives
from spc_platform.common.types import BoolArray, FloatArray
from spc_platform.domain.ids import RuleId

ZONE_A = 3.0
"""Outer zone edge: beyond three standard errors."""

ZONE_B = 2.0
"""Middle zone edge: beyond two standard errors."""

ZONE_C = 1.0
"""Inner zone edge: beyond one standard error."""


@dataclass(frozen=True, slots=True)
class RuleContext:
    """Everything a rule reads about a panel.

    Attributes
    ----------
    standardised
        Distances from the centre line in standard errors. Limit-based rules
        use these, which is what lets them work unchanged on charts whose
        limits move from point to point.
    values
        The plotted statistic in its own units. Trend and sawtooth rules use
        these: a trend is a property of the process, and standardising by a
        per-point standard error could manufacture or erase one when the
        sample size changes.
    """

    standardised: FloatArray
    values: FloatArray


@dataclass(frozen=True, slots=True)
class Rule:
    """One run rule: what it detects, how much history it needs, and its source.

    Attributes
    ----------
    rule_id
        Configuration identity, e.g. ``WE-2``.
    description
        The published wording, close enough to be recognised by a quality
        engineer reading a violation record.
    window
        Points the rule needs before it can signal at all. Reported on the rule
        so the application can say "not enough history yet" rather than
        silently returning no violations.
    detect
        Vectorised test over a whole panel.
    """

    rule_id: RuleId
    description: str
    window: int
    detect: Callable[[RuleContext], BoolArray]


def _beyond_three_sigma(context: RuleContext) -> BoolArray:
    return primitives.beyond(context.standardised, ZONE_A)


def _two_of_three_beyond_two_sigma(context: RuleContext) -> BoolArray:
    return primitives.k_of_m_beyond(context.standardised, k=2, m=3, threshold=ZONE_B)


def _four_of_five_beyond_one_sigma(context: RuleContext) -> BoolArray:
    return primitives.k_of_m_beyond(context.standardised, k=4, m=5, threshold=ZONE_C)


def _eight_on_one_side(context: RuleContext) -> BoolArray:
    return primitives.run_on_one_side(context.standardised, length=8)


def _nine_on_one_side(context: RuleContext) -> BoolArray:
    return primitives.run_on_one_side(context.standardised, length=9)


def _six_trending(context: RuleContext) -> BoolArray:
    return primitives.monotonic_run(context.values, length=6)


def _fourteen_alternating(context: RuleContext) -> BoolArray:
    return primitives.alternating_run(context.values, length=14)


def _fifteen_hugging(context: RuleContext) -> BoolArray:
    return primitives.run_within(context.standardised, length=15, threshold=ZONE_C)


def _eight_straddling(context: RuleContext) -> BoolArray:
    return primitives.run_outside_straddling(context.standardised, length=8, threshold=ZONE_C)


WESTERN_ELECTRIC_1 = RuleId("WE-1")
WESTERN_ELECTRIC_2 = RuleId("WE-2")
WESTERN_ELECTRIC_3 = RuleId("WE-3")
WESTERN_ELECTRIC_4 = RuleId("WE-4")

NELSON_1 = RuleId("NELSON-1")
NELSON_2 = RuleId("NELSON-2")
NELSON_3 = RuleId("NELSON-3")
NELSON_4 = RuleId("NELSON-4")
NELSON_5 = RuleId("NELSON-5")
NELSON_6 = RuleId("NELSON-6")
NELSON_7 = RuleId("NELSON-7")
NELSON_8 = RuleId("NELSON-8")

_RULES: tuple[Rule, ...] = (
    Rule(
        rule_id=WESTERN_ELECTRIC_1,
        description="One point beyond zone A (three sigma from the centre line)",
        window=1,
        detect=_beyond_three_sigma,
    ),
    Rule(
        rule_id=WESTERN_ELECTRIC_2,
        description="Two of three consecutive points beyond two sigma, same side",
        window=3,
        detect=_two_of_three_beyond_two_sigma,
    ),
    Rule(
        rule_id=WESTERN_ELECTRIC_3,
        description="Four of five consecutive points beyond one sigma, same side",
        window=5,
        detect=_four_of_five_beyond_one_sigma,
    ),
    Rule(
        rule_id=WESTERN_ELECTRIC_4,
        description="Eight consecutive points on one side of the centre line",
        window=8,
        detect=_eight_on_one_side,
    ),
    Rule(
        rule_id=NELSON_1,
        description="One point beyond three sigma from the centre line",
        window=1,
        detect=_beyond_three_sigma,
    ),
    Rule(
        rule_id=NELSON_2,
        description="Nine consecutive points on one side of the centre line",
        window=9,
        detect=_nine_on_one_side,
    ),
    Rule(
        rule_id=NELSON_3,
        description="Six consecutive points steadily increasing or decreasing",
        window=6,
        detect=_six_trending,
    ),
    Rule(
        rule_id=NELSON_4,
        description="Fourteen consecutive points alternating up and down",
        window=14,
        detect=_fourteen_alternating,
    ),
    Rule(
        rule_id=NELSON_5,
        description="Two of three consecutive points beyond two sigma, same side",
        window=3,
        detect=_two_of_three_beyond_two_sigma,
    ),
    Rule(
        rule_id=NELSON_6,
        description="Four of five consecutive points beyond one sigma, same side",
        window=5,
        detect=_four_of_five_beyond_one_sigma,
    ),
    Rule(
        rule_id=NELSON_7,
        description="Fifteen consecutive points within one sigma, either side",
        window=15,
        detect=_fifteen_hugging,
    ),
    Rule(
        rule_id=NELSON_8,
        description="Eight consecutive points beyond one sigma on both sides",
        window=8,
        detect=_eight_straddling,
    ),
)

CATALOGUE: MappingProxyType[RuleId, Rule] = MappingProxyType(
    {rule.rule_id: rule for rule in _RULES}
)
"""Every rule the platform can be configured to run, by identity.

Read-only so that no caller can register a rule at runtime. A rule that is not
in this module has no published source and no measured average run length, and
adding one is a change to statistical behaviour (FR-R06).
"""

WESTERN_ELECTRIC: tuple[RuleId, ...] = (
    WESTERN_ELECTRIC_1,
    WESTERN_ELECTRIC_2,
    WESTERN_ELECTRIC_3,
    WESTERN_ELECTRIC_4,
)
"""The four rules whose combined in-control ARL Montgomery gives as 91.75."""

NELSON: tuple[RuleId, ...] = (
    NELSON_1,
    NELSON_2,
    NELSON_3,
    NELSON_4,
    NELSON_5,
    NELSON_6,
    NELSON_7,
    NELSON_8,
)
"""Nelson's eight tests, in his numbering."""
