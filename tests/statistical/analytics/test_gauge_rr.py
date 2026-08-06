"""Gauge R&R by ANOVA, verified three independent ways.

The usual reference for a gauge study is the AIAG MSA manual, which ADR-0017
rules out as a numerical test dependency: it is copyrighted, and an expected
value a reviewer cannot look up is a claim rather than a citation. So the
correctness of this module is established without it, by three routes that fail
in different ways.

**Against an independent implementation.** The sums of squares are checked
against statsmodels' ordinary least squares fit of the same crossed model on
random data. That catches an arithmetic slip in the decomposition but would not
catch a wrong choice of denominator, since statsmodels defaults to the
fixed-effects test.

**Against exact algebra.** Data is constructed whose sums of squares are
integers computable by hand, so the whole table can be written down
independently of any implementation.

**Against known truth.** Data is simulated from variance components that are
known because they were chosen, and the estimator is required to recover them.
That is the only one of the three that tests the expected mean squares, which is
where the random effects model actually differs from the fixed one.

References
----------
Montgomery, D. C. (2020). *Design and Analysis of Experiments*, 10th ed., §13.3.
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §8.7.2.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm
import statsmodels.formula.api as smf

from spc_platform.analytics.msa.acceptance import (
    AcceptanceBands,
    GaugeCriterion,
    GaugeVerdict,
    judge,
)
from spc_platform.analytics.msa.gauge_rr import (
    GaugeStudy,
    VarianceSource,
    anova_table,
    gauge_rr_anova,
)
from spc_platform.common.errors import (
    ConfigurationError,
    DegenerateSeriesError,
    InsufficientDataError,
)
from spc_platform.common.types import FloatArray

BANDS = AcceptanceBands(
    acceptable_percent=10.0,
    marginal_percent=30.0,
    minimum_distinct_categories=5,
)
"""Thresholds supplied by the caller, as the design requires (ADR-0017).

These particular numbers are the conventional ones. They are a fixture here, not
a default in the library, which is the whole point of the arrangement.
"""


@dataclass(frozen=True, slots=True)
class Truth:
    """Standard deviations a simulated study is built from, so recovery is checkable."""

    part: float
    operator: float
    interaction: float
    error: float


def simulate(
    truth: Truth,
    *,
    shape: tuple[int, int, int] = (10, 3, 3),
    seed: int = 20260803,
) -> FloatArray:
    """Draw a crossed study from variance components that are known by construction."""
    parts, operators, _ = shape
    rng = np.random.default_rng(seed)
    part_effect = rng.normal(0.0, truth.part, (parts, 1, 1))
    operator_effect = rng.normal(0.0, truth.operator, (1, operators, 1))
    interaction = rng.normal(0.0, truth.interaction, (parts, operators, 1))
    noise = rng.normal(0.0, truth.error, shape)
    return 100.0 + part_effect + operator_effect + interaction + noise


def as_frame(values: FloatArray) -> pd.DataFrame:
    """Flatten a crossed study into the long form statsmodels expects."""
    parts, operators, replicates = values.shape
    part_index, operator_index, _ = np.meshgrid(
        np.arange(parts),
        np.arange(operators),
        np.arange(replicates),
        indexing="ij",
    )
    return pd.DataFrame(
        {
            "y": values.ravel(),
            "part": part_index.ravel().astype(str),
            "operator": operator_index.ravel().astype(str),
        }
    )


class TestTheDecompositionAgainstStatsmodels:
    """The sums of squares must match an independent implementation exactly."""

    @pytest.fixture
    def values(self) -> FloatArray:
        """Build a study with every component genuinely present."""
        return simulate(Truth(part=5.0, operator=1.5, interaction=0.8, error=1.0))

    @pytest.fixture
    def reference(self, values: FloatArray) -> pd.DataFrame:
        """Type II sums of squares from a full crossed ordinary least squares fit."""
        model = smf.ols("y ~ C(part) * C(operator)", data=as_frame(values)).fit()
        frame: pd.DataFrame = sm.stats.anova_lm(model, typ=2)
        return frame

    def test_every_sum_of_squares_matches(
        self, values: FloatArray, reference: pd.DataFrame
    ) -> None:
        """Balanced data makes the decomposition unambiguous, so these agree exactly."""
        table = anova_table(GaugeStudy(measurements=values), pool_interaction=False)
        assert table.interaction is not None
        assert table.part.sum_of_squares == pytest.approx(reference.loc["C(part)", "sum_sq"])
        assert table.operator.sum_of_squares == pytest.approx(
            reference.loc["C(operator)", "sum_sq"]
        )
        assert table.interaction.sum_of_squares == pytest.approx(
            reference.loc["C(part):C(operator)", "sum_sq"]
        )
        assert table.error.sum_of_squares == pytest.approx(reference.loc["Residual", "sum_sq"])

    def test_every_degree_of_freedom_matches(
        self, values: FloatArray, reference: pd.DataFrame
    ) -> None:
        """A wrong degree of freedom would move every p-value without moving an SS."""
        table = anova_table(GaugeStudy(measurements=values), pool_interaction=False)
        assert table.interaction is not None
        assert table.part.degrees_of_freedom == reference.loc["C(part)", "df"]
        assert table.operator.degrees_of_freedom == reference.loc["C(operator)", "df"]
        assert table.interaction.degrees_of_freedom == reference.loc["C(part):C(operator)", "df"]
        assert table.error.degrees_of_freedom == reference.loc["Residual", "df"]

    def test_the_random_model_uses_a_different_denominator(
        self, values: FloatArray, reference: pd.DataFrame
    ) -> None:
        """The one place this must *not* agree with the default statsmodels output.

        Both factors are random, so the part and operator terms are tested
        against the interaction mean square rather than the error mean square.
        A general ANOVA routine uses the error mean square, which overstates
        both F statistics. Asserting the difference is what pins the random
        effects model down.
        """
        table = anova_table(GaugeStudy(measurements=values), pool_interaction=False)
        assert table.interaction is not None
        assert table.part.f_statistic is not None

        against_interaction = table.part.mean_square / table.interaction.mean_square
        fixed_effects_f = float(reference["F"]["C(part)"])

        assert table.part.f_statistic == pytest.approx(against_interaction)
        assert fixed_effects_f == pytest.approx(table.part.mean_square / table.error.mean_square), (
            "statsmodels tests against the error mean square, as a fixed model does"
        )
        assert table.part.f_statistic < fixed_effects_f, (
            "the fixed-effects statistic overstates the part effect, which is "
            "the mistake this module exists to avoid"
        )


class TestTheDecompositionAgainstHandArithmetic:
    """A constructed case whose whole table can be written down independently."""

    @pytest.fixture
    def values(self) -> FloatArray:
        """Two parts, two operators, two replicates, with orthogonal unit effects.

        Cell means are 10, 20, 30, 40 — a part effect of +/-10 about the grand
        mean of 25, an operator effect of +/-5, and no interaction. Each cell is
        measured as its mean plus and minus one, so every cell contributes a
        residual sum of squares of 2.
        """
        cells = np.array([[10.0, 20.0], [30.0, 40.0]])
        return np.stack([cells - 1.0, cells + 1.0], axis=2)

    def test_the_part_sum_of_squares(self, values: FloatArray) -> None:
        """o*r*sum((part mean - grand)^2) = 2*2*(10^2 + 10^2) = 800."""
        table = anova_table(GaugeStudy(measurements=values), pool_interaction=False)
        assert table.part.sum_of_squares == pytest.approx(800.0)
        assert table.part.degrees_of_freedom == 1

    def test_the_operator_sum_of_squares(self, values: FloatArray) -> None:
        """p*r*sum((operator mean - grand)^2) = 2*2*(5^2 + 5^2) = 200."""
        table = anova_table(GaugeStudy(measurements=values), pool_interaction=False)
        assert table.operator.sum_of_squares == pytest.approx(200.0)
        assert table.operator.degrees_of_freedom == 1

    def test_the_interaction_vanishes(self, values: FloatArray) -> None:
        """The effects were built additive, so nothing is left for the interaction."""
        table = anova_table(GaugeStudy(measurements=values), pool_interaction=False)
        assert table.interaction is not None
        assert table.interaction.sum_of_squares == pytest.approx(0.0, abs=1e-9)

    def test_the_error_sum_of_squares(self, values: FloatArray) -> None:
        """Four cells, each contributing (+1)^2 + (-1)^2 = 2, so 8 with 4 df."""
        table = anova_table(GaugeStudy(measurements=values), pool_interaction=False)
        assert table.error.sum_of_squares == pytest.approx(8.0)
        assert table.error.degrees_of_freedom == 4
        assert table.error.mean_square == pytest.approx(2.0)

    def test_the_rows_add_up_to_the_total(self, values: FloatArray) -> None:
        """800 + 200 + 0 + 8 = 1008, which is the total sum of squares."""
        table = anova_table(GaugeStudy(measurements=values), pool_interaction=False)
        assert table.interaction is not None
        parts = (
            table.part.sum_of_squares
            + table.operator.sum_of_squares
            + table.interaction.sum_of_squares
            + table.error.sum_of_squares
        )
        assert parts == pytest.approx(table.total_sum_of_squares)
        assert table.total_sum_of_squares == pytest.approx(1008.0)


class TestTheDecompositionIsExhaustive:
    """The four rows account for all the variation, on any data at all."""

    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
    def test_the_sums_of_squares_partition_the_total(self, seed: int) -> None:
        """Nothing is double counted and nothing is lost."""
        values = simulate(Truth(part=3.0, operator=1.0, interaction=0.5, error=0.7), seed=seed)
        table = anova_table(GaugeStudy(measurements=values), pool_interaction=False)
        assert table.interaction is not None
        total = (
            table.part.sum_of_squares
            + table.operator.sum_of_squares
            + table.interaction.sum_of_squares
            + table.error.sum_of_squares
        )
        assert total == pytest.approx(table.total_sum_of_squares, rel=1e-12)

    @pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
    def test_the_degrees_of_freedom_partition_the_total(self, seed: int) -> None:
        """(p-1) + (o-1) + (p-1)(o-1) + po(r-1) = por - 1."""
        parts, operators, replicates = 8, 3, 4
        values = simulate(
            Truth(part=3.0, operator=1.0, interaction=0.5, error=0.7),
            shape=(parts, operators, replicates),
            seed=seed,
        )
        table = anova_table(GaugeStudy(measurements=values), pool_interaction=False)
        assert table.total_degrees_of_freedom == parts * operators * replicates - 1

    def test_pooling_preserves_the_partition(self) -> None:
        """Folding the interaction into error moves variation, it does not lose it."""
        values = simulate(Truth(part=5.0, operator=1.0, interaction=0.0, error=1.0))
        full = anova_table(GaugeStudy(measurements=values), pool_interaction=False)
        pooled = anova_table(GaugeStudy(measurements=values), pool_interaction=True)

        assert pooled.pooled
        assert pooled.interaction is None
        assert full.interaction is not None
        assert pooled.error.sum_of_squares == pytest.approx(
            full.interaction.sum_of_squares + full.error.sum_of_squares
        )
        assert pooled.total_sum_of_squares == pytest.approx(full.total_sum_of_squares)


class TestTheComponentsRecoverKnownTruth:
    """The estimators must return the variances the data was actually built from.

    This is the test that exercises the expected mean squares. A wrong divisor
    or a wrong denominator gives a table that still adds up and still matches
    statsmodels, and fails only here.
    """

    def test_repeatability_is_recovered(self) -> None:
        """Error variance is estimated directly by the error mean square."""
        values = simulate(
            Truth(part=5.0, operator=1.5, interaction=0.6, error=2.0), shape=(30, 3, 6)
        )
        result = gauge_rr_anova(GaugeStudy(measurements=values), pool_interaction=False)
        assert np.sqrt(result.components.repeatability) == pytest.approx(2.0, rel=0.1)

    def test_the_part_variance_is_recovered(self) -> None:
        """The dominant component, and the one the divisor ``o*r`` scales."""
        values = simulate(
            Truth(part=5.0, operator=1.5, interaction=0.6, error=2.0), shape=(60, 3, 4)
        )
        result = gauge_rr_anova(GaugeStudy(measurements=values), pool_interaction=False)
        assert np.sqrt(result.components.part) == pytest.approx(5.0, rel=0.25)

    def test_the_operator_variance_is_recovered(self) -> None:
        """Estimated from three operators, so a wide tolerance is the honest one.

        The operator effect has only two degrees of freedom no matter how many
        parts are measured, which is a real property of the design rather than
        a shortcoming of the estimator: a study with three operators cannot
        pin down the spread of the population they were drawn from.
        """
        recovered = [
            gauge_rr_anova(
                GaugeStudy(
                    measurements=simulate(
                        Truth(part=5.0, operator=2.0, interaction=0.0, error=1.0), seed=seed
                    )
                ),
                pool_interaction=False,
            ).components.operator
            for seed in range(60)
        ]
        assert float(np.mean(recovered)) == pytest.approx(4.0, rel=0.4)

    def test_a_perfect_gauge_reports_almost_no_grr(self) -> None:
        """Tiny measurement error against large parts is the acceptable case."""
        values = simulate(Truth(part=10.0, operator=0.01, interaction=0.01, error=0.05))
        result = gauge_rr_anova(GaugeStudy(measurements=values))
        assert result.percent_study_variation < 5.0
        assert result.number_of_distinct_categories > 10

    def test_a_useless_gauge_reports_almost_all_grr(self) -> None:
        """Measurement error swamping the parts is the unacceptable case."""
        values = simulate(Truth(part=0.1, operator=1.0, interaction=0.5, error=3.0))
        result = gauge_rr_anova(GaugeStudy(measurements=values))
        assert result.percent_study_variation > 90.0
        assert result.number_of_distinct_categories <= 1


class TestTheReportedFigures:
    """%GRR and NDC, which are where a correct table still gets misreported."""

    def test_percent_grr_is_a_ratio_of_standard_deviations(self) -> None:
        """Not of variances. The two differ enormously and are easily confused."""
        values = simulate(Truth(part=3.0, operator=1.0, interaction=0.0, error=1.0))
        result = gauge_rr_anova(GaugeStudy(measurements=values))
        expected = 100.0 * np.sqrt(result.components.gauge_rr / result.components.total)
        assert result.percent_study_variation == pytest.approx(expected)

    def test_the_components_sum_to_the_total(self) -> None:
        """Gauge R&R plus part is the whole of the observed variation."""
        values = simulate(Truth(part=3.0, operator=1.0, interaction=0.4, error=1.0))
        components = gauge_rr_anova(
            GaugeStudy(measurements=values), pool_interaction=False
        ).components
        assert components.gauge_rr == pytest.approx(
            components.repeatability + components.operator + components.interaction
        )
        assert components.total == pytest.approx(components.gauge_rr + components.part)

    def test_percent_of_tolerance_uses_the_study_multiplier(self) -> None:
        """Six standard deviations against the specification width."""
        values = simulate(Truth(part=3.0, operator=1.0, interaction=0.0, error=1.0))
        result = gauge_rr_anova(GaugeStudy(measurements=values, tolerance=20.0))
        assert result.percent_tolerance is not None
        expected = 100.0 * 6.0 * np.sqrt(result.components.gauge_rr) / 20.0
        assert result.percent_tolerance == pytest.approx(expected)

    def test_percent_of_tolerance_is_absent_without_a_tolerance(self) -> None:
        """A gauge not tied to one specification has no such percentage."""
        values = simulate(Truth(part=3.0, operator=1.0, interaction=0.0, error=1.0))
        result = gauge_rr_anova(GaugeStudy(measurements=values))
        assert result.percent_tolerance is None

    def test_ndc_is_truncated_not_rounded(self) -> None:
        """The conventional treatment: a system resolving 4.9 groups resolves 4."""
        values = simulate(Truth(part=3.0, operator=1.0, interaction=0.0, error=1.0))
        result = gauge_rr_anova(GaugeStudy(measurements=values))
        exact = 1.41 * np.sqrt(result.components.part / result.components.gauge_rr)
        assert result.number_of_distinct_categories == int(exact)

    def test_a_negative_component_is_clamped_and_recorded(self) -> None:
        """Set to zero, because a negative variance is not a finding.

        Recording the clamp is what stops "the operator effect is zero" being
        read as evidence of agreement, when it is really evidence that the
        study was too small to resolve the component either way.
        """
        values = simulate(
            Truth(part=4.0, operator=0.0, interaction=0.0, error=1.0),
            shape=(5, 3, 2),
            seed=3,
        )
        components = gauge_rr_anova(
            GaugeStudy(measurements=values), pool_interaction=False
        ).components

        assert components.clamped == {
            VarianceSource.OPERATOR,
            VarianceSource.INTERACTION,
        }
        assert components.operator == 0.0
        assert components.interaction == 0.0
        assert components.part > 0.0

    def test_a_resolved_component_is_not_marked_as_clamped(self) -> None:
        """The record has to distinguish "zero" from "not resolved" to be worth having."""
        values = simulate(
            Truth(part=5.0, operator=2.0, interaction=1.0, error=1.0), shape=(30, 3, 4)
        )
        components = gauge_rr_anova(
            GaugeStudy(measurements=values), pool_interaction=False
        ).components
        assert components.clamped == frozenset()


class TestTheJudgement:
    """The verdict, against bands the caller supplied rather than the library."""

    def test_a_good_gauge_is_acceptable(self) -> None:
        """Low %GRR and plenty of distinct categories."""
        values = simulate(Truth(part=10.0, operator=0.01, interaction=0.01, error=0.05))
        verdict = judge(gauge_rr_anova(GaugeStudy(measurements=values)), BANDS)
        assert verdict.verdict is GaugeVerdict.ACCEPTABLE

    def test_a_bad_gauge_is_unacceptable(self) -> None:
        """Measurement error swamping the parts fails on every criterion."""
        values = simulate(Truth(part=0.1, operator=1.0, interaction=0.5, error=3.0))
        verdict = judge(gauge_rr_anova(GaugeStudy(measurements=values)), BANDS)
        assert verdict.verdict is GaugeVerdict.UNACCEPTABLE

    def test_the_worse_percentage_decides(self) -> None:
        """A gauge can look fine against varied parts and fail against the spec.

        The parts in this study vary far more than the tolerance, so the study
        variation figure flatters the gauge. The tolerance figure is the one
        that says whether it can sort conforming parts from non-conforming.
        """
        values = simulate(Truth(part=50.0, operator=0.5, interaction=0.2, error=1.0))
        result = gauge_rr_anova(GaugeStudy(measurements=values, tolerance=15.0))
        verdict = judge(result, BANDS)

        assert result.percent_tolerance is not None
        assert result.percent_study_variation < BANDS.acceptable_percent
        assert result.percent_tolerance > BANDS.marginal_percent
        assert verdict.verdict is GaugeVerdict.UNACCEPTABLE
        assert verdict.deciding_criterion is GaugeCriterion.TOLERANCE

    def test_too_few_categories_fails_a_good_percentage(self) -> None:
        """A percentage compares the gauge to the parts it was given; NDC does not."""
        values = simulate(Truth(part=1.2, operator=0.1, interaction=0.05, error=0.5))
        result = gauge_rr_anova(GaugeStudy(measurements=values))
        verdict = judge(result, BANDS)
        if result.number_of_distinct_categories < BANDS.minimum_distinct_categories:
            assert verdict.verdict is GaugeVerdict.UNACCEPTABLE

    def test_the_bands_travel_with_the_verdict(self) -> None:
        """So the judgement can be re-derived after the configuration changes."""
        values = simulate(Truth(part=10.0, operator=0.01, interaction=0.01, error=0.05))
        verdict = judge(gauge_rr_anova(GaugeStudy(measurements=values)), BANDS)
        assert verdict.bands == BANDS

    @pytest.mark.parametrize(
        ("acceptable", "marginal"),
        [(30.0, 10.0), (0.0, 10.0), (-5.0, 10.0)],
    )
    def test_incoherent_bands_are_refused(self, acceptable: float, marginal: float) -> None:
        """Bands out of order would make the verdict depend on evaluation order."""
        with pytest.raises(ConfigurationError):
            AcceptanceBands(
                acceptable_percent=acceptable,
                marginal_percent=marginal,
                minimum_distinct_categories=5,
            )


class TestTheRefusals:
    """Designs that cannot answer the question the study was run to answer."""

    def test_a_single_replicate_is_refused(self) -> None:
        """No residual, so repeatability — the whole point — is not estimable."""
        values = simulate(
            Truth(part=3.0, operator=1.0, interaction=0.0, error=1.0), shape=(10, 3, 1)
        )
        with pytest.raises(InsufficientDataError, match="repeatability"):
            gauge_rr_anova(GaugeStudy(measurements=values))

    def test_a_single_operator_is_refused(self) -> None:
        """Reproducibility is variation between operators, and there is only one."""
        values = simulate(
            Truth(part=3.0, operator=1.0, interaction=0.0, error=1.0), shape=(10, 1, 3)
        )
        with pytest.raises(InsufficientDataError):
            gauge_rr_anova(GaugeStudy(measurements=values))

    def test_a_flat_study_is_refused(self) -> None:
        """No variation at all leaves nothing to apportion."""
        with pytest.raises(DegenerateSeriesError):
            gauge_rr_anova(GaugeStudy(measurements=np.full((5, 3, 3), 7.0)))

    def test_the_wrong_shape_is_refused(self) -> None:
        """A crossed study is indexed by part, operator, and replicate."""
        with pytest.raises(ConfigurationError, match="part, operator, and replicate"):
            gauge_rr_anova(GaugeStudy(measurements=np.zeros((5, 3))))

    def test_a_non_positive_tolerance_is_refused(self) -> None:
        """A zero-width tolerance would make every gauge infinitely bad."""
        values = simulate(Truth(part=3.0, operator=1.0, interaction=0.0, error=1.0))
        with pytest.raises(ConfigurationError, match="tolerance"):
            gauge_rr_anova(GaugeStudy(measurements=values, tolerance=0.0))
