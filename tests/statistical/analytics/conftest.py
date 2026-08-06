"""Panel builders for the analytics statistical tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from spc_platform.analytics.charts import DEFAULT_SIGMA_MULTIPLIER
from spc_platform.common.types import FloatArray
from spc_platform.domain.chart_spec import RuleDefinition, RuleSet
from spc_platform.domain.charting import ChartLimits, ChartPanel, PlottedSeries
from spc_platform.domain.enums import (
    ChartStatistic,
    ChartType,
    SigmaEstimator,
    ViolationSeverity,
)
from spc_platform.domain.ids import BaselineId, ParameterId, RuleId, UnitSymbol

EPOCH = datetime(2026, 1, 1, tzinfo=UTC)
"""Start of every synthetic series here. Any aware instant would do."""

PARAMETER = ParameterId("POLY_CD")
BASELINE = BaselineId("BL-0001")
UNIT = UnitSymbol("nm")


def timestamps_for(count: int) -> tuple[datetime, ...]:
    """One aware timestamp per point, an hour apart."""
    return tuple(EPOCH + timedelta(hours=index) for index in range(count))


@pytest.fixture
def standard_panel() -> PanelFactory:
    """Build a panel whose plotted values are already in standard errors."""
    return PanelFactory()


class PanelFactory:
    """Makes panels with a centre of zero and unit spread.

    Values supplied to it are therefore both the plotted statistic and its
    standardised form, which is what makes a rule's expected behaviour legible
    in the test: a value of 3.1 is a point just past the three sigma limit.
    """

    def __call__(
        self,
        values: Sequence[float] | FloatArray,
        *,
        centre_line: float = 0.0,
        sigma_statistic: float = 1.0,
        statistic: ChartStatistic = ChartStatistic.INDIVIDUAL,
        chart_type: ChartType = ChartType.I_MR,
    ) -> ChartPanel:
        """Assemble a panel from plotted values."""
        plotted = tuple(float(value) for value in values)
        reach = DEFAULT_SIGMA_MULTIPLIER * sigma_statistic
        series = PlottedSeries(
            parameter_id=PARAMETER,
            chart_type=chart_type,
            statistic=statistic,
            unit=UNIT,
            values=plotted,
            timestamps=timestamps_for(len(plotted)),
            subgroup_sizes=(1,),
        )
        limits = ChartLimits(
            parameter_id=PARAMETER,
            baseline_id=BASELINE,
            chart_type=chart_type,
            statistic=statistic,
            unit=UNIT,
            centre_line=(centre_line,),
            lcl=(centre_line - reach,),
            ucl=(centre_line + reach,),
            sigma_statistic=(sigma_statistic,),
            sigma_multiplier=DEFAULT_SIGMA_MULTIPLIER,
            sigma_estimator=SigmaEstimator.MR_BAR_D2,
            sigma_process=sigma_statistic,
        )
        return ChartPanel(series=series, limits=limits)


def rule_set_of(*rule_ids: RuleId, name: str = "test-set") -> RuleSet:
    """Build a rule set running the given rules, all at warning severity."""
    return RuleSet(
        name=name,
        rules=tuple(
            RuleDefinition(rule_id=rule_id, severity=ViolationSeverity.WARNING)
            for rule_id in rule_ids
        ),
    )


def alternating(count: int, amplitude: float = 0.5) -> FloatArray:
    """Build a sawtooth of ``count`` points, staying well inside the limits."""
    signs = np.where(np.arange(count) % 2 == 0, 1.0, -1.0)
    return amplitude * signs
