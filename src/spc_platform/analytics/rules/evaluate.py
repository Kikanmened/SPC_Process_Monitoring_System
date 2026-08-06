"""Applying a configured rule set to a chart panel.

One pass over the panel per rule, each vectorised, producing a violation for
every point a rule signalled on. Rules are evaluated independently and their
signals are not merged: if three rules fire on the same point, three violations
are recorded. Collapsing them would lose the reason, and the reason is what
tells an engineer whether to look for a shift, a trend, or a mixture.
"""

from __future__ import annotations

import numpy as np

from spc_platform.analytics.charts.panels import standardised
from spc_platform.analytics.rules.catalogue import CATALOGUE, Rule, RuleContext
from spc_platform.common.errors import ConfigurationError
from spc_platform.domain.chart_spec import RuleSet
from spc_platform.domain.charting import ChartPanel, ControlChart
from spc_platform.domain.ids import RuleId
from spc_platform.domain.violation import Violation


def evaluate_panel(rule_set: RuleSet, panel: ChartPanel) -> tuple[Violation, ...]:
    """Every violation a rule set finds on one panel, in point order.

    Parameters
    ----------
    rule_set
        Rules to apply, each with the severity to record.
    panel
        The plotted series and the limits it is judged against.

    Returns
    -------
    tuple of Violation
        Ordered by point index, then by the order the rules were configured in.
        Deterministic ordering matters because these records are compared
        between runs during validation.

    Raises
    ------
    ConfigurationError
        If the rule set names a rule that has no implementation, which means a
        configuration file references a rule that was never published or was
        renamed without migrating the configuration.
    """
    context = RuleContext(
        standardised=standardised(panel),
        values=np.asarray(panel.series.values, dtype=np.float64),
    )
    found: list[Violation] = []
    for definition in rule_set.rules:
        rule = _rule_for(definition.rule_id)
        signalled = rule.detect(context)
        for index in np.flatnonzero(signalled):
            point = int(index)
            found.append(
                Violation(
                    parameter_id=panel.series.parameter_id,
                    baseline_id=panel.limits.baseline_id,
                    rule_id=rule.rule_id,
                    chart_type=panel.series.chart_type,
                    severity=definition.severity,
                    point_index=point,
                    timestamp=panel.series.timestamps[point],
                    statistic_value=panel.series.values[point],
                )
            )
    return tuple(sorted(found, key=lambda violation: violation.point_index))


def evaluate_chart(rule_set: RuleSet, chart: ControlChart) -> tuple[Violation, ...]:
    """Every violation across both panels of a chart.

    The dispersion panel is evaluated with the same rule set as the location
    panel, which is the conventional treatment and the one the published ARL
    figures assume.

    Parameters
    ----------
    rule_set
        Rules to apply.
    chart
        Location panel and, where the family has one, dispersion panel.

    Returns
    -------
    tuple of Violation
        Location panel violations first, then dispersion.

    Raises
    ------
    ConfigurationError
        If the rule set names a rule with no implementation.
    """
    return tuple(
        violation for panel in chart.panels for violation in evaluate_panel(rule_set, panel)
    )


def insufficient_history(rule_set: RuleSet, points: int) -> tuple[RuleId, ...]:
    """Rules that cannot signal yet because the series is too short.

    A rule needing fifteen points is not passing on a twelve-point series; it
    has not run. The distinction matters on a new tool, where a chart of a
    dozen points can look reassuringly clean simply because most of the
    configured rules are still dormant.

    Parameters
    ----------
    rule_set
        Rules configured for the parameter.
    points
        Plotted points available.

    Returns
    -------
    tuple of RuleId
        Rules whose window exceeds the available history, in configured order.

    Raises
    ------
    ConfigurationError
        If the rule set names a rule with no implementation.
    """
    return tuple(
        definition.rule_id
        for definition in rule_set.rules
        if _rule_for(definition.rule_id).window > points
    )


def _rule_for(rule_id: RuleId) -> Rule:
    """Look up a configured rule, refusing an unknown identity.

    Raises
    ------
    ConfigurationError
        If no rule with this identity is published in the catalogue.
    """
    try:
        return CATALOGUE[rule_id]
    except KeyError:
        raise ConfigurationError(
            "no rule with this identity is implemented",
            rule_id=rule_id,
            available=sorted(CATALOGUE),
        ) from None
