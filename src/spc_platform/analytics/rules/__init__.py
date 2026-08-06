"""Run rules: the published pattern tests and the cost of switching them on.

The catalogue holds the rules, ``evaluate`` applies a configured set to a
panel, and ``arl`` measures what that set does to the false alarm rate. The
third is not optional decoration — a rule set without its measured average run
length is a change to alarm behaviour whose magnitude nobody has established
(FR-R05).
"""

from spc_platform.analytics.rules.arl import (
    DEFAULT_MAX_POINTS,
    DEFAULT_RUNS,
    ArlResult,
    measure_arl,
)
from spc_platform.analytics.rules.catalogue import (
    CATALOGUE,
    NELSON,
    WESTERN_ELECTRIC,
    ZONE_A,
    ZONE_B,
    ZONE_C,
    Rule,
    RuleContext,
)
from spc_platform.analytics.rules.evaluate import (
    evaluate_chart,
    evaluate_panel,
    insufficient_history,
)

__all__ = [
    "CATALOGUE",
    "DEFAULT_MAX_POINTS",
    "DEFAULT_RUNS",
    "NELSON",
    "WESTERN_ELECTRIC",
    "ZONE_A",
    "ZONE_B",
    "ZONE_C",
    "ArlResult",
    "Rule",
    "RuleContext",
    "evaluate_chart",
    "evaluate_panel",
    "insufficient_history",
    "measure_arl",
]
