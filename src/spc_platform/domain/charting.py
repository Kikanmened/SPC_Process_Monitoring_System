"""What a control chart plots: the statistic, its limits, and its zones.

Distinct from ``ControlLimit``, which is the qualified process boundary a
``Baseline`` carries. The types here describe one drawn panel: the X-bar panel
of an X-bar/R chart has a different centre line and different limit width from
the R panel beside it, and both are derived from the single ``ControlLimit``
the baseline holds.

`MODULE_DESIGN.md` module 3 calls this ``ControlLimits``. It is ``ChartLimits``
here, because a codebase containing both ``ControlLimit`` and ``ControlLimits``
would eventually have someone import the wrong one, and the two are not
interchangeable — one is the approved process boundary, the other is a drawing
instruction derived from it.

Limits are stored per point. A chart whose limits never move stores one value
and NumPy broadcasting makes it apply to every point; a p chart with a
different sample size at every point stores one value per point. Nothing
downstream needs to know which case it has, which is what keeps the rule engine
free of special cases for variable limits.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from spc_platform.domain._time import require_aware
from spc_platform.domain.enums import ChartStatistic, ChartType, SigmaEstimator
from spc_platform.domain.errors import DomainInvariantError
from spc_platform.domain.ids import BaselineId, ParameterId, UnitSymbol

CONSTANT_LIMIT_LENGTH = 1
"""A single stored value means the limit is the same at every point."""


class ChartLimits(BaseModel):
    """Centre line, control limits, and zone width for one plotted panel.

    Every sequence field holds either one value, meaning constant, or one value
    per plotted point. Mixing the two is allowed and intended: a u chart has a
    constant centre line and limits that move with the inspection size.

    Attributes
    ----------
    centre_line
        Where the statistic is expected to sit.
    lcl, ucl
        Action limits. Already truncated where the statistic has a floor — a
        range or a proportion cannot go below zero — so a consumer never has to
        know which charts need clipping.

        Either may be absent, which means the panel does not signal on that
        side at all. That is not the same as a limit sitting at zero: an R chart
        with small subgroups has a real lower limit of zero, and a range of
        exactly zero is a legitimate signal against it, whereas a CUSUM arm has
        no lower limit and a value of zero on it is the most in-control reading
        there is. Collapsing the two cases would make one of them wrong.
    sigma_statistic
        Standard deviation of one plotted point, which is what the zones are
        multiples of. **Not** the process sigma: on an X-bar chart with
        subgroups of five it is the process sigma over the square root of five.
    sigma_process
        The process sigma the panel was derived from, retained so a chart can
        state what it was drawn with.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    baseline_id: BaselineId
    chart_type: ChartType
    statistic: ChartStatistic
    unit: UnitSymbol
    centre_line: tuple[float, ...] = Field(min_length=1)
    lcl: tuple[float, ...] | None = Field(default=None, min_length=1)
    ucl: tuple[float, ...] | None = Field(default=None, min_length=1)
    sigma_statistic: tuple[float, ...] = Field(min_length=1)
    sigma_multiplier: float = Field(gt=0)
    sigma_estimator: SigmaEstimator
    sigma_process: float = Field(gt=0)

    @model_validator(mode="after")
    def _invariants(self) -> ChartLimits:
        if self.lcl is None and self.ucl is None:
            raise DomainInvariantError(
                "a panel with no limit on either side cannot signal",
                statistic=self.statistic,
            )
        lengths = {len(self.centre_line), len(self.sigma_statistic)} | {
            len(bound) for bound in (self.lcl, self.ucl) if bound is not None
        }
        varying = lengths - {CONSTANT_LIMIT_LENGTH}
        if len(varying) > 1:
            raise DomainInvariantError(
                "per-point limits must all cover the same number of points",
                lengths=sorted(lengths),
            )
        if any(width <= 0.0 for width in self.sigma_statistic):
            raise DomainInvariantError(
                "a plotted point with zero spread has no zones and no limits",
                sigma_statistic=self.sigma_statistic,
            )
        self._require_ordered_limits()
        return self

    def _require_ordered_limits(self) -> None:
        """Check every limit that exists sits on the correct side of its centre line.

        Raises
        ------
        DomainInvariantError
            If any point has ``lcl >= centre_line`` or ``centre_line >= ucl``.
            A limit equal to the centre line would signal on a point that is
            behaving exactly as expected.
        """
        present = [len(bound) for bound in (self.lcl, self.ucl) if bound is not None]
        points = max(len(self.centre_line), *present, CONSTANT_LIMIT_LENGTH)
        for index in range(points):
            centre = _at(self.centre_line, index)
            lower = None if self.lcl is None else _at(self.lcl, index)
            upper = None if self.ucl is None else _at(self.ucl, index)
            if (lower is not None and lower >= centre) or (upper is not None and upper <= centre):
                raise DomainInvariantError(
                    "require lcl < centre_line < ucl for every limit present",
                    point_index=index,
                    lcl=lower,
                    centre_line=centre,
                    ucl=upper,
                )

    @property
    def is_constant(self) -> bool:
        """Whether one set of limits applies to every point."""
        sequences = (self.centre_line, self.lcl, self.ucl, self.sigma_statistic)
        return all(
            len(values) == CONSTANT_LIMIT_LENGTH for values in sequences if values is not None
        )


class PlottedSeries(BaseModel):
    """The statistic actually drawn, point by point, with its provenance.

    Attributes
    ----------
    values
        The plotted statistic — individuals, subgroup means, ranges, EWMA, or
        a CUSUM arm — in plotting order.
    timestamps
        When each point was produced. Same length as ``values``, so a violation
        can be reported at a time rather than an index.
    subgroup_sizes
        Observations behind each point; one value if every point has the same
        size. Retained because the limits depend on it and a reader of a chart
        cannot otherwise tell a mean of 3 from a mean of 25.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    parameter_id: ParameterId
    chart_type: ChartType
    statistic: ChartStatistic
    unit: UnitSymbol
    values: tuple[float, ...] = Field(min_length=1)
    timestamps: tuple[datetime, ...] = Field(min_length=1)
    subgroup_sizes: tuple[int, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _invariants(self) -> PlottedSeries:
        if len(self.timestamps) != len(self.values):
            raise DomainInvariantError(
                "every plotted point needs its own timestamp",
                values=len(self.values),
                timestamps=len(self.timestamps),
            )
        if len(self.subgroup_sizes) not in {CONSTANT_LIMIT_LENGTH, len(self.values)}:
            raise DomainInvariantError(
                "subgroup sizes must be one value or one per point",
                values=len(self.values),
                subgroup_sizes=len(self.subgroup_sizes),
            )
        if any(size < 1 for size in self.subgroup_sizes):
            raise DomainInvariantError(
                "a plotted point summarises at least one observation",
                subgroup_sizes=self.subgroup_sizes,
            )
        for index, moment in enumerate(self.timestamps):
            require_aware(moment, field_name=f"timestamps[{index}]")
        return self

    def __len__(self) -> int:
        """Count the plotted points."""
        return len(self.values)


class ChartPanel(BaseModel):
    """One drawn panel: a series and the limits it is judged against.

    The two always travel together. Separating them is how a chart ends up
    drawn against limits from a superseded baseline, which renders perfectly
    and is wrong.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    series: PlottedSeries
    limits: ChartLimits

    @model_validator(mode="after")
    def _invariants(self) -> ChartPanel:
        if self.series.statistic is not self.limits.statistic:
            raise DomainInvariantError(
                "a panel's limits must be for the statistic it plots",
                series=self.series.statistic,
                limits=self.limits.statistic,
            )
        if self.series.parameter_id != self.limits.parameter_id:
            raise DomainInvariantError(
                "a panel's limits must be for the parameter it plots",
                series=self.series.parameter_id,
                limits=self.limits.parameter_id,
            )
        if not self.limits.is_constant:
            self._require_limit_coverage()
        return self

    def _require_limit_coverage(self) -> None:
        """Check per-point limits cover exactly the points plotted.

        Raises
        ------
        DomainInvariantError
            If a varying limit sequence is a different length from the series.
        """
        sequences = {
            "centre_line": self.limits.centre_line,
            "lcl": self.limits.lcl,
            "ucl": self.limits.ucl,
            "sigma_statistic": self.limits.sigma_statistic,
        }
        points = len(self.series)
        for name, values in sequences.items():
            if values is None:
                continue
            if len(values) not in {CONSTANT_LIMIT_LENGTH, points}:
                raise DomainInvariantError(
                    "per-point limits must cover every plotted point",
                    field=name,
                    length=len(values),
                    points=points,
                )


class ControlChart(BaseModel):
    """A location panel and, for the paired charts, its dispersion panel.

    I-MR, X-bar/R, and X-bar/S are pairs, and reading either panel alone is a
    known way to miss a change: a process can hold its mean perfectly while its
    spread doubles. Keeping both in one object means a caller cannot ask for
    half of a paired chart without noticing.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    location: ChartPanel
    dispersion: ChartPanel | None = None

    @model_validator(mode="after")
    def _invariants(self) -> ControlChart:
        if self.dispersion is None:
            return self
        if self.dispersion.series.chart_type is not self.location.series.chart_type:
            raise DomainInvariantError(
                "both panels of a chart describe the same chart type",
                location=self.location.series.chart_type,
                dispersion=self.dispersion.series.chart_type,
            )
        return self

    @property
    def panels(self) -> tuple[ChartPanel, ...]:
        """Every panel present, location first."""
        if self.dispersion is None:
            return (self.location,)
        return (self.location, self.dispersion)


def _at(values: tuple[float, ...], index: int) -> float:
    """Read a possibly-constant sequence at a point index."""
    if len(values) == CONSTANT_LIMIT_LENGTH:
        return values[0]
    return values[index]
