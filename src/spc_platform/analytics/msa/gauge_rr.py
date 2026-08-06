r"""Gauge R&R by the ANOVA method (FR-M01, FR-M02).

Every control chart in this platform plots the sum of the process and the
instrument that measured it. A gauge study is what separates the two, and it is
the precondition for everything else here rather than a side report: if the
measurement system consumes 40% of the tolerance, a Cpk computed from that data
describes an artefact, and a chart drawn from it is substantially plotting the
gauge.

The ANOVA method is used rather than the average-and-range method, for one
reason that matters. The range method cannot estimate the part-by-operator
interaction at all — it folds that variation into reproducibility, or loses it.
An interaction is the finding that one operator measures large parts high and
another measures them low, which is a real and common failure of a manual gauge
and is invisible to the older method. ANOVA also gives the components a
sampling distribution, so the interaction can be tested rather than assumed.

Three things here are deliberate and easy to get wrong.

**Negative variance components are set to zero, and the fact is recorded.** The
estimators are differences of mean squares, so sampling noise can drive one
below zero. Reporting a negative variance is meaningless and silently clamping
it hides that the study was too small to resolve the component. Both the clamp
and its cause are on the result.

**A non-significant interaction is pooled into error, on request.** With the
interaction retained, its mean square is the denominator for the operator term,
and when the interaction is pure noise that denominator is needlessly imprecise.
Pooling is the conventional remedy above a significance of 0.25 — a deliberately
lax threshold, because the cost of wrongly keeping a null interaction is small
and the cost of wrongly pooling a real one is not.

**The acceptance bands are not here.** They are configuration
(:mod:`spc_platform.analytics.msa.acceptance`, ADR-0017). This module computes
%GRR and NDC; what counts as acceptable is a decision an organisation makes and
records, not a constant compiled into a library.

References
----------
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §8.7 (gauge capability), §8.7.2 (the ANOVA method).
Montgomery, D. C. (2020). *Design and Analysis of Experiments*, 10th ed., §13.3
(random effects models and expected mean squares).
Burdick, R. K., Borror, C. M. and Montgomery, D. C. (2003). "A Review of Methods
for Measurement Systems Capability Analysis." *Journal of Quality Technology*
35(4), 342-354.
NIST/SEMATECH e-Handbook of Statistical Methods, §2.4 (gauge R&R).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
from scipy import stats

from spc_platform.common.errors import (
    ConfigurationError,
    DegenerateSeriesError,
    InsufficientDataError,
)
from spc_platform.common.types import FloatArray

MIN_PARTS = 2
MIN_OPERATORS = 2
MIN_REPLICATES = 2
"""Two replicates is the arithmetic minimum for repeatability to exist at all.

With one measurement per part per operator there is no residual degree of
freedom, so the instrument's own repeatability is not estimable and the study
cannot answer the question it was run to answer. Ten parts, three operators, and
three replicates is the conventional size; this constant only guards the
division.
"""

DEFAULT_POOLING_SIGNIFICANCE = 0.25
"""Above this the interaction is treated as absent and pooled into error.

Deliberately lax. Wrongly keeping a null interaction costs a little precision;
wrongly pooling a real one hides the finding that two operators disagree about
which parts are large, which is the failure the ANOVA method exists to detect.
"""

DEFAULT_STUDY_VARIATION_MULTIPLIER = 6.0
"""Standard deviations spanned when expressing a component as a width.

Six covers 99.73% of a normal distribution and matches the six-sigma width the
capability indices use, so %GRR of tolerance and Cp are on the same footing.
Older practice used 5.15, for 99%; a study reporting one is not comparable with
a study reporting the other, so the multiplier travels with the result.
"""

NDC_MULTIPLIER = 1.41
r"""Distinct categories per unit of the part-to-part to gauge standard deviation ratio.

:math:`\sqrt{2}`, to two decimals, as the number of non-overlapping confidence
intervals the measurement system can resolve across the part range. Quoted as
1.41 throughout the literature, so it is written that way here rather than as
``sqrt(2)``, which would silently differ in the fourth decimal from every
published figure it is compared against.
"""


class VarianceSource(StrEnum):
    """Where a component of the observed variation came from."""

    PART = "part"
    OPERATOR = "operator"
    INTERACTION = "interaction"
    REPEATABILITY = "repeatability"


@dataclass(frozen=True, slots=True)
class AnovaTerm:
    """One row of the ANOVA table.

    Attributes
    ----------
    source
        What the row is for.
    sum_of_squares, degrees_of_freedom, mean_square
        The usual decomposition. ``mean_square`` is the sum of squares over the
        degrees of freedom.
    f_statistic, p_value
        Test against the correct denominator for a random effects model, which
        is the interaction mean square for the part and operator terms rather
        than the error mean square. Absent for the error row, which is the
        thing everything else is tested against.
    """

    source: VarianceSource
    sum_of_squares: float
    degrees_of_freedom: int
    mean_square: float
    f_statistic: float | None = None
    p_value: float | None = None


@dataclass(frozen=True, slots=True)
class AnovaTable:
    """The full decomposition, retained so a result can be audited rather than trusted.

    Attributes
    ----------
    part, operator, interaction, error
        The four rows. ``interaction`` is ``None`` once it has been pooled.
    total_sum_of_squares, total_degrees_of_freedom
        The decomposition these rows must add up to.
    pooled
        Whether the interaction was pooled into error.
    """

    part: AnovaTerm
    operator: AnovaTerm
    error: AnovaTerm
    total_sum_of_squares: float
    total_degrees_of_freedom: int
    interaction: AnovaTerm | None = None
    pooled: bool = False


@dataclass(frozen=True, slots=True)
class VarianceComponents:
    """The variances the study set out to separate, in squared measurement units.

    Attributes
    ----------
    repeatability
        Equipment variation: the same operator, the same part, twice.
    operator
        Reproducibility's main effect: operators differing on average.
    interaction
        Operators disagreeing about which parts are large. Zero once pooled.
    part
        The variation the process actually has, which is the only component
        anybody wants to see on a chart.
    clamped
        Components that came out negative and were set to zero. A non-empty
        set means the study was too small to resolve them, and the components
        that were clamped should be read as "not resolved", not as "absent".
    """

    repeatability: float
    operator: float
    interaction: float
    part: float
    clamped: frozenset[VarianceSource] = frozenset()

    @property
    def reproducibility(self) -> float:
        """Operator effect plus interaction: variation between people, not machines."""
        return self.operator + self.interaction

    @property
    def gauge_rr(self) -> float:
        """Everything the measurement system contributes."""
        return self.repeatability + self.reproducibility

    @property
    def total(self) -> float:
        """Gauge plus part: the variation a control chart would actually see."""
        return self.gauge_rr + self.part


@dataclass(frozen=True, slots=True)
class GaugeStudy:
    """A balanced crossed study: every operator measures every part, equally often.

    Attributes
    ----------
    measurements
        Shape ``(parts, operators, replicates)``. Balanced by construction —
        an unbalanced study needs restricted maximum likelihood rather than the
        closed-form mean squares here, and silently averaging it away would
        misstate the degrees of freedom and therefore every test in the table.
    tolerance
        Width of the specification the gauge is used against, for %GRR of
        tolerance. ``None`` when the gauge is not tied to one specification.
    """

    measurements: FloatArray
    tolerance: float | None = None

    @property
    def n_parts(self) -> int:
        """Parts in the study."""
        return int(self.measurements.shape[0])

    @property
    def n_operators(self) -> int:
        """Operators in the study."""
        return int(self.measurements.shape[1])

    @property
    def n_replicates(self) -> int:
        """Measurements of each part by each operator."""
        return int(self.measurements.shape[2])


@dataclass(frozen=True, slots=True)
class GaugeRRResult:
    """What the study concluded, with everything needed to check it (FR-M02).

    Attributes
    ----------
    components
        The separated variances.
    anova
        The table they were derived from.
    study_variation_multiplier
        Standard deviations spanned by the reported widths.
    tolerance
        The specification width, if one was supplied.
    n_parts, n_operators, n_replicates
        The design.
    """

    components: VarianceComponents
    anova: AnovaTable
    study_variation_multiplier: float
    n_parts: int
    n_operators: int
    n_replicates: int
    tolerance: float | None = None

    @property
    def percent_study_variation(self) -> float:
        """%GRR against total observed variation.

        Computed on standard deviations, not variances. The two give different
        numbers — 30% of the standard deviation is 9% of the variance — and
        which one is meant is the single most common ambiguity in a gauge
        report. The convention throughout is the standard deviation ratio.
        """
        return 100.0 * float(np.sqrt(self.components.gauge_rr / self.components.total))

    @property
    def percent_tolerance(self) -> float | None:
        """%GRR against the specification width, or ``None`` without one.

        The more demanding of the two figures in practice. A gauge can look
        excellent against a sloppy process and still be unable to sort
        conforming parts from non-conforming ones.
        """
        if self.tolerance is None:
            return None
        width = self.study_variation_multiplier * float(np.sqrt(self.components.gauge_rr))
        return 100.0 * width / self.tolerance

    @property
    def number_of_distinct_categories(self) -> int:
        """How many groups the gauge can actually tell apart across the part range.

        Truncated, not rounded, following the usual convention: a system that
        resolves 4.9 categories resolves 4. Five is the conventional minimum
        for a gauge used to make decisions about individual parts; below two
        the gauge can only say "same or different".
        """
        if self.components.gauge_rr <= 0.0:
            return 0
        ratio = float(np.sqrt(self.components.part / self.components.gauge_rr))
        return int(NDC_MULTIPLIER * ratio)


def gauge_rr_anova(
    study: GaugeStudy,
    *,
    pool_interaction: bool = True,
    pooling_significance: float = DEFAULT_POOLING_SIGNIFICANCE,
    study_variation_multiplier: float = DEFAULT_STUDY_VARIATION_MULTIPLIER,
) -> GaugeRRResult:
    r"""Separate the measurement system's variation from the process's.

    The model is fully random, every factor being a sample from a population:

    .. math::
        y_{ijk} = \mu + P_i + O_j + (PO)_{ij} + \varepsilon_{ijk}

    which fixes the expected mean squares and therefore the estimators:

    .. math::
        \hat\sigma^2_\varepsilon = MS_E, \qquad
        \hat\sigma^2_{PO} = \frac{MS_{PO} - MS_E}{r} \\
        \hat\sigma^2_{O} = \frac{MS_{O} - MS_{PO}}{pr}, \qquad
        \hat\sigma^2_{P} = \frac{MS_{P} - MS_{PO}}{or}

    Note what the denominators are. The operator and part terms are tested
    against the *interaction* mean square, not the error mean square, because
    both factors are random. Using the error mean square — which is what a
    fixed-effects ANOVA routine does by default, and what a spreadsheet almost
    always does — overstates both F statistics, often by a large factor, and
    turns an unremarkable study into a significant one.

    Parameters
    ----------
    study
        A balanced crossed study, shaped ``(parts, operators, replicates)``.
    pool_interaction
        Pool a non-significant interaction into error.
    pooling_significance
        Above this p-value the interaction is treated as absent.
    study_variation_multiplier
        Standard deviations spanned when reporting a component as a width.

    Returns
    -------
    GaugeRRResult
        Components, the ANOVA table, %GRR, and NDC.

    Raises
    ------
    InsufficientDataError
        If the design is too small for the components to be estimable — in
        particular, with one replicate there is no repeatability.
    DegenerateSeriesError
        If every measurement is identical, so there is no variation to divide.
    ConfigurationError
        If the measurements are not a three-dimensional balanced array, or the
        tolerance is not positive.

    References
    ----------
    Montgomery (2019), 8th ed., §8.7.2. Montgomery (2020), *Design and Analysis
    of Experiments*, 10th ed., §13.3. Burdick, Borror and Montgomery (2003),
    *Journal of Quality Technology* 35(4).
    """
    _require_design(study)
    table = anova_table(
        study,
        pool_interaction=pool_interaction,
        pooling_significance=pooling_significance,
    )
    return GaugeRRResult(
        components=_components(study, table),
        anova=table,
        study_variation_multiplier=study_variation_multiplier,
        tolerance=study.tolerance,
        n_parts=study.n_parts,
        n_operators=study.n_operators,
        n_replicates=study.n_replicates,
    )


def anova_table(
    study: GaugeStudy,
    *,
    pool_interaction: bool = True,
    pooling_significance: float = DEFAULT_POOLING_SIGNIFICANCE,
) -> AnovaTable:
    """Decompose the total variation into part, operator, interaction, and error.

    Parameters
    ----------
    study
        A balanced crossed study.
    pool_interaction
        Pool a non-significant interaction into error.
    pooling_significance
        Above this p-value the interaction is treated as absent.

    Returns
    -------
    AnovaTable
        The four rows and the totals they add up to.

    References
    ----------
    Montgomery (2020), *Design and Analysis of Experiments*, 10th ed., §13.3.
    """
    values = study.measurements
    parts, operators, replicates = values.shape

    grand = float(np.mean(values))
    by_part = np.mean(values, axis=(1, 2))
    by_operator = np.mean(values, axis=(0, 2))
    by_cell = np.mean(values, axis=2)

    ss_part = operators * replicates * float(np.sum((by_part - grand) ** 2))
    ss_operator = parts * replicates * float(np.sum((by_operator - grand) ** 2))
    residual = by_cell - by_part[:, None] - by_operator[None, :] + grand
    ss_interaction = replicates * float(np.sum(residual**2))
    ss_error = float(np.sum((values - by_cell[:, :, None]) ** 2))
    ss_total = float(np.sum((values - grand) ** 2))

    df_part = parts - 1
    df_operator = operators - 1
    df_interaction = df_part * df_operator
    df_error = parts * operators * (replicates - 1)

    interaction_p = _p_value(
        ss_interaction / df_interaction if df_interaction else 0.0,
        ss_error / df_error,
        df_interaction,
        df_error,
    )
    pooled = bool(
        pool_interaction
        and df_interaction > 0
        and interaction_p is not None
        and interaction_p > pooling_significance
    )
    if pooled:
        return _pooled_table(
            _Sums(ss_part, ss_operator, ss_interaction, ss_error, ss_total),
            _Frames(df_part, df_operator, df_interaction, df_error),
        )
    return _full_table(
        _Sums(ss_part, ss_operator, ss_interaction, ss_error, ss_total),
        _Frames(df_part, df_operator, df_interaction, df_error),
        interaction_p,
    )


@dataclass(frozen=True, slots=True)
class _Sums:
    """Sums of squares, passed as a unit to keep the table builders readable."""

    part: float
    operator: float
    interaction: float
    error: float
    total: float


@dataclass(frozen=True, slots=True)
class _Frames:
    """Degrees of freedom matching :class:`_Sums`."""

    part: int
    operator: int
    interaction: int
    error: int


def _full_table(sums: _Sums, frames: _Frames, interaction_p: float | None) -> AnovaTable:
    """Build the table with the interaction retained as its own term.

    Both random factors are tested against the interaction mean square, which
    is what makes this a random effects analysis rather than the fixed-effects
    one a general ANOVA routine would produce.
    """
    ms_interaction = sums.interaction / frames.interaction if frames.interaction else 0.0
    ms_error = sums.error / frames.error
    return AnovaTable(
        part=_term(VarianceSource.PART, sums.part, frames.part, ms_interaction, frames.interaction),
        operator=_term(
            VarianceSource.OPERATOR,
            sums.operator,
            frames.operator,
            ms_interaction,
            frames.interaction,
        ),
        interaction=AnovaTerm(
            source=VarianceSource.INTERACTION,
            sum_of_squares=sums.interaction,
            degrees_of_freedom=frames.interaction,
            mean_square=ms_interaction,
            f_statistic=ms_interaction / ms_error if ms_error > 0.0 else None,
            p_value=interaction_p,
        ),
        error=AnovaTerm(
            source=VarianceSource.REPEATABILITY,
            sum_of_squares=sums.error,
            degrees_of_freedom=frames.error,
            mean_square=ms_error,
        ),
        total_sum_of_squares=sums.total,
        total_degrees_of_freedom=frames.part + frames.operator + frames.interaction + frames.error,
        pooled=False,
    )


def _pooled_table(sums: _Sums, frames: _Frames) -> AnovaTable:
    """Build the table with a non-significant interaction folded into error.

    The pooled error carries both sums of squares and both degrees of freedom,
    which is the whole benefit: a more precise estimate of repeatability, and
    therefore a more precise test of the operator effect.
    """
    ss_error = sums.interaction + sums.error
    df_error = frames.interaction + frames.error
    ms_error = ss_error / df_error
    return AnovaTable(
        part=_term(VarianceSource.PART, sums.part, frames.part, ms_error, df_error),
        operator=_term(VarianceSource.OPERATOR, sums.operator, frames.operator, ms_error, df_error),
        interaction=None,
        error=AnovaTerm(
            source=VarianceSource.REPEATABILITY,
            sum_of_squares=ss_error,
            degrees_of_freedom=df_error,
            mean_square=ms_error,
        ),
        total_sum_of_squares=sums.total,
        total_degrees_of_freedom=frames.part + frames.operator + df_error,
        pooled=True,
    )


def _term(
    source: VarianceSource,
    sum_of_squares: float,
    degrees_of_freedom: int,
    denominator_ms: float,
    denominator_df: int,
) -> AnovaTerm:
    """Build one tested row against the denominator the random model requires."""
    mean_square = sum_of_squares / degrees_of_freedom if degrees_of_freedom else 0.0
    return AnovaTerm(
        source=source,
        sum_of_squares=sum_of_squares,
        degrees_of_freedom=degrees_of_freedom,
        mean_square=mean_square,
        f_statistic=mean_square / denominator_ms if denominator_ms > 0.0 else None,
        p_value=_p_value(mean_square, denominator_ms, degrees_of_freedom, denominator_df),
    )


def _p_value(
    numerator_ms: float,
    denominator_ms: float,
    numerator_df: int,
    denominator_df: int,
) -> float | None:
    """Upper tail of the F distribution, or ``None`` where the test does not exist."""
    if numerator_df <= 0 or denominator_df <= 0 or denominator_ms <= 0.0:
        return None
    ratio = numerator_ms / denominator_ms
    return float(stats.f.sf(ratio, numerator_df, denominator_df))


def _components(study: GaugeStudy, table: AnovaTable) -> VarianceComponents:
    """Invert the expected mean squares, clamping at zero and saying which.

    The estimators are differences of mean squares, so a component whose true
    value is near zero comes out negative about half the time. Zero is the only
    defensible report, and recording the clamp is what stops it being read as
    evidence of a genuinely absent effect.
    """
    parts = study.n_parts
    operators = study.n_operators
    replicates = study.n_replicates

    repeatability = table.error.mean_square
    # With the interaction pooled away, the error mean square is the correct
    # denominator for both remaining terms; with it retained, it is not.
    denominator = (
        table.error.mean_square if table.interaction is None else table.interaction.mean_square
    )
    interaction = (
        0.0
        if table.interaction is None
        else (table.interaction.mean_square - table.error.mean_square) / replicates
    )
    operator = (table.operator.mean_square - denominator) / (parts * replicates)
    part = (table.part.mean_square - denominator) / (operators * replicates)

    clamped = {
        source
        for source, value in (
            (VarianceSource.INTERACTION, interaction),
            (VarianceSource.OPERATOR, operator),
            (VarianceSource.PART, part),
        )
        if value < 0.0
    }
    return VarianceComponents(
        repeatability=repeatability,
        operator=max(0.0, operator),
        interaction=max(0.0, interaction),
        part=max(0.0, part),
        clamped=frozenset(clamped),
    )


def _require_design(study: GaugeStudy) -> None:
    """Refuse a study whose shape cannot answer the question it was run for.

    Raises
    ------
    ConfigurationError
        If the measurements are not three-dimensional, or the tolerance is not
        positive.
    InsufficientDataError
        If any factor is too small, in particular a single replicate.
    DegenerateSeriesError
        If every measurement is identical.
    """
    expected_dimensions = 3
    if study.measurements.ndim != expected_dimensions:
        raise ConfigurationError(
            "a crossed gauge study is indexed by part, operator, and replicate",
            shape=study.measurements.shape,
        )
    if study.tolerance is not None and study.tolerance <= 0.0:
        raise ConfigurationError(
            "a tolerance width must be positive",
            tolerance=study.tolerance,
        )
    for name, size, minimum in (
        ("parts", study.n_parts, MIN_PARTS),
        ("operators", study.n_operators, MIN_OPERATORS),
        ("replicates", study.n_replicates, MIN_REPLICATES),
    ):
        if size < minimum:
            raise InsufficientDataError(
                "a single replicate leaves no residual, so repeatability — the "
                "thing a gauge study exists to measure — is not estimable"
                if name == "replicates"
                else f"a gauge study needs at least {minimum} {name}",
                factor=name,
                n=size,
                required=minimum,
            )
    if float(np.ptp(study.measurements)) <= 0.0:
        raise DegenerateSeriesError(
            "every measurement is identical, so no variation can be apportioned",
            n=int(study.measurements.size),
        )
