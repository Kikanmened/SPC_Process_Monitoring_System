"""Nested variance decomposition, verified four independent ways.

**Against a published table.** Montgomery's raw-material purity example is a
three-supplier, four-batch, three-determination nested design with an ANOVA
table printed in the text. Every sum of squares, degree of freedom, and mean
square is checked against it, and so is the negative supplier component the
text remarks on — the case a naive implementation silently reports as zero.

**Against exact algebra on a balanced design.** The unbalanced coefficients
this module computes must collapse to the textbook ``bn`` and ``n`` when the
design happens to be balanced. That is checked directly on the coefficient
matrix, because it is the one property that would let a subtle error in the
general formula hide behind correct answers on tidy data.

**Against known truth.** Components are recovered from data simulated with
components that are known because they were chosen.

**Against simulated expectations on a deliberately ragged design.** This is the
one that matters. The expected sums of squares under an unbalanced hierarchy are
the part no textbook table covers, so they are checked by simulating the model
many times and requiring the average sum of squares at each level to match what
the coefficient matrix predicts.

References
----------
Montgomery, D. C. (2020). *Design and Analysis of Experiments*, 10th ed.,
§14.1 and Example 14.1 (the two-stage nested design).
Searle, S. R., Casella, G. and McCulloch, C. E. (1992). *Variance Components*,
Wiley, §4.3 (unbalanced nested classifications).
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

import numpy as np
import pytest

from spc_platform.analytics.variance import (
    HENDERSON_METHOD_I,
    LOT_WAFER_SITE_MODEL,
    NestedMeasurements,
    NestedVarianceResult,
    VarianceModel,
    decompose_variance,
)
from spc_platform.analytics.variance.nested import _coefficients, _design, _table
from spc_platform.common.errors import (
    ConfigurationError,
    DegenerateSeriesError,
    InsufficientDataError,
)
from spc_platform.common.types import FloatArray, IntArray

PURITY_MODEL = VarianceModel(levels=("supplier", "batch"), residual="determination")
"""The hierarchy of Montgomery's Example 14.1."""


@dataclass(frozen=True, slots=True)
class Truth:
    """Standard deviations a simulated hierarchy is built from, so recovery is checkable."""

    lot: float
    wafer: float
    site: float

    @property
    def variances(self) -> FloatArray:
        """The components in the order the coefficient matrix expects them.

        Prefixed with a zero for the grand mean, which is a level in the design
        but carries no variance component of its own.
        """
        return np.array([0.0, self.lot**2, self.wafer**2, self.site**2])


def balanced_factors(lots: int, wafers: int, sites: int) -> IntArray:
    """Return lot and wafer codes for a fully balanced hierarchy.

    Wafer codes restart at zero in every lot, which is what a slot number does
    and is the input the path-based cell identity exists to handle.
    """
    lot_codes = np.repeat(np.arange(lots), wafers * sites)
    wafer_codes = np.tile(np.repeat(np.arange(wafers), sites), lots)
    return np.vstack([lot_codes, wafer_codes])


def simulate_balanced(truth: Truth, shape: tuple[int, int, int], *, seed: int = 0) -> FloatArray:
    """Draw a balanced lot/wafer/site hierarchy from known components."""
    lots, wafers, sites = shape
    generator = np.random.default_rng(seed)
    lot_effect = generator.normal(0.0, truth.lot, (lots, 1, 1))
    wafer_effect = generator.normal(0.0, truth.wafer, (lots, wafers, 1))
    site_effect = generator.normal(0.0, truth.site, (lots, wafers, sites))
    values = 100.0 + lot_effect + wafer_effect + site_effect
    return np.asarray(values.ravel(), dtype=np.float64)


@functools.cache
def ragged_factors() -> IntArray:
    """Return a deliberately unbalanced hierarchy: 2-5 wafers a lot, 1-4 sites a wafer.

    Cached because the design is fixed data rather than a per-test fixture, and
    the simulation below reuses it a few thousand times.
    """
    generator = np.random.default_rng(5)
    lot_codes: list[int] = []
    wafer_codes: list[int] = []
    for lot in range(25):
        for wafer in range(int(generator.integers(2, 6))):
            sites = int(generator.integers(1, 5))
            lot_codes += [lot] * sites
            wafer_codes += [wafer] * sites
    return np.vstack([np.array(lot_codes), np.array(wafer_codes)])


def draw_on(factors: IntArray, truth: Truth, generator: np.random.Generator) -> FloatArray:
    """Draw one realisation of the nested model over an arbitrary design.

    Effects are drawn per cell and expanded back over the observations, so an
    unbalanced design gets the same effect on every observation in a cell,
    which is what makes the term a variance component rather than noise.
    """
    design = _design(NestedMeasurements(values=np.zeros(factors.shape[1]), factors=factors))
    lot_effect = generator.normal(0.0, truth.lot, len(design.sizes[1]))[design.codes[1]]
    wafer_effect = generator.normal(0.0, truth.wafer, len(design.sizes[2]))[design.codes[2]]
    site_effect = generator.normal(0.0, truth.site, factors.shape[1])
    return np.asarray(100.0 + lot_effect + wafer_effect + site_effect, dtype=np.float64)


@functools.cache
def purity_study() -> NestedVarianceResult:
    """Montgomery Example 14.1: purity by supplier, batch within supplier.

    Coded observations exactly as printed. Three suppliers, four batches from
    each, three determinations of purity per batch.
    """
    values = np.array(
        [
            [[1, -1, 0], [-2, -3, -4], [-2, 0, 1], [1, 4, 0]],
            [[1, -2, -3], [0, 4, 2], [-1, 0, -2], [0, 3, 2]],
            [[2, 4, 0], [-2, 0, 2], [1, -1, 2], [3, 2, 1]],
        ],
        dtype=np.float64,
    )
    data = NestedMeasurements(values=values.ravel(), factors=balanced_factors(3, 4, 3))
    return decompose_variance(data, PURITY_MODEL)


class TestTheMontgomeryPurityExample:
    """The published nested ANOVA table, reproduced row by row."""

    @pytest.mark.parametrize(
        ("level", "expected"),
        [("supplier", 15.06), ("batch", 69.92), ("determination", 63.33)],
    )
    def test_the_sums_of_squares_match_the_published_table(
        self, level: str, expected: float
    ) -> None:
        """Montgomery, DAE 10th ed., Example 14.1, printed to two decimals."""
        row = {term.name: term for term in purity_study().table}[level]
        assert row.sum_of_squares == pytest.approx(expected, abs=0.005)

    @pytest.mark.parametrize(
        ("level", "expected"),
        [("supplier", 2), ("batch", 9), ("determination", 24)],
    )
    def test_the_degrees_of_freedom_match_the_published_table(
        self, level: str, expected: int
    ) -> None:
        """a-1, a(b-1), and ab(n-1) for three suppliers, four batches, three runs."""
        row = {term.name: term for term in purity_study().table}[level]
        assert row.degrees_of_freedom == expected

    @pytest.mark.parametrize(
        ("level", "expected"),
        [("supplier", 7.53), ("batch", 7.77), ("determination", 2.64)],
    )
    def test_the_mean_squares_match_the_published_table(self, level: str, expected: float) -> None:
        """The three mean squares as printed, to two decimals."""
        row = {term.name: term for term in purity_study().table}[level]
        assert row.mean_square == pytest.approx(expected, abs=0.005)

    def test_the_supplier_component_is_negative_and_therefore_clamped(self) -> None:
        """The text's own remark on this data, and the case a naive routine hides.

        The supplier mean square is *smaller* than the batch mean square, so the
        estimator returns a negative variance. Reporting zero without saying so
        would read as "suppliers agree", when what the data supports is "this
        study could not tell suppliers apart from batches within them".
        """
        supplier = purity_study().components[0]
        assert supplier.name == "supplier"
        assert supplier.clamped
        assert supplier.variance == 0.0

    def test_the_batch_and_determination_components_are_resolved(self) -> None:
        """Batch and error come out positive, so only the supplier row is clamped."""
        _, batch, determination = purity_study().components
        assert not batch.clamped
        assert not determination.clamped
        assert batch.variance == pytest.approx((7.7685 - 2.6389) / 3.0, rel=1e-3)
        assert determination.variance == pytest.approx(2.6389, rel=1e-3)


class TestTheDecompositionIsExhaustive:
    """Whatever the design, the parts must add up to the whole."""

    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_the_sums_of_squares_partition_the_total(self, seed: int) -> None:
        """Nesting is an orthogonal decomposition, so this is exact, not approximate."""
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (12, 4, 3), seed=seed)
        data = NestedMeasurements(values=values, factors=balanced_factors(12, 4, 3))
        result = decompose_variance(data)
        about_grand_mean = float(np.sum((values - values.mean()) ** 2))
        assert sum(term.sum_of_squares for term in result.table) == pytest.approx(
            about_grand_mean, rel=1e-12
        )

    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_the_degrees_of_freedom_partition_the_total(self, seed: int) -> None:
        """(a-1) + a(b-1) + ab(n-1) = abn - 1."""
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (12, 4, 3), seed=seed)
        data = NestedMeasurements(values=values, factors=balanced_factors(12, 4, 3))
        result = decompose_variance(data)
        assert sum(term.degrees_of_freedom for term in result.table) == 12 * 4 * 3 - 1

    def test_the_partition_holds_on_a_ragged_design_too(self) -> None:
        """The property is not an artefact of balance."""
        factors = ragged_factors()
        values = draw_on(factors, Truth(3.0, 2.0, 1.0), np.random.default_rng(1))
        result = decompose_variance(NestedMeasurements(values=values, factors=factors))
        about_grand_mean = float(np.sum((values - values.mean()) ** 2))
        assert sum(term.sum_of_squares for term in result.table) == pytest.approx(
            about_grand_mean, rel=1e-12
        )
        assert sum(term.degrees_of_freedom for term in result.table) == factors.shape[1] - 1

    def test_the_shares_add_to_one_hundred_percent(self) -> None:
        """Shares are taken on variances, which is what makes them add up."""
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (20, 4, 3))
        result = decompose_variance(
            NestedMeasurements(values=values, factors=balanced_factors(20, 4, 3))
        )
        shares = [result.percent_of(name) for name in result.model.names]
        assert sum(shares) == pytest.approx(100.0, rel=1e-12)


class TestTheBalancedCaseCollapsesToTheTextbookCoefficients:
    """The general formula must reproduce the special case exactly."""

    def test_the_expected_mean_squares_take_the_published_form(self) -> None:
        r"""E[MS_lot] = s2 + n*w2 + bn*l2, E[MS_wafer] = s2 + n*w2, E[MS_site] = s2.

        Montgomery, DAE 10th ed., §14.1.3. The coefficient matrix here is built
        from the general unbalanced formula, so agreeing with these three
        expressions on balanced data is a real check of it rather than a
        restatement.
        """
        lots, wafers, sites = 7, 5, 4
        data = NestedMeasurements(
            values=np.zeros(lots * wafers * sites),
            factors=balanced_factors(lots, wafers, sites),
        )
        design = _design(data)
        coefficients = _coefficients(design)
        degrees = np.array([0, lots - 1, lots * (wafers - 1), lots * wafers * (sites - 1)])

        # Row 1 is the lot term, row 2 the wafer term, row 3 the residual.
        assert coefficients[1, 1] / degrees[1] == pytest.approx(wafers * sites)
        assert coefficients[1, 2] / degrees[1] == pytest.approx(sites)
        assert coefficients[1, 3] / degrees[1] == pytest.approx(1.0)
        assert coefficients[2, 2] / degrees[2] == pytest.approx(sites)
        assert coefficients[2, 3] / degrees[2] == pytest.approx(1.0)
        assert coefficients[3, 3] / degrees[3] == pytest.approx(1.0)

    def test_no_level_carries_variation_from_above_it(self) -> None:
        """The coefficient matrix is upper triangular, by the structure of nesting."""
        data = NestedMeasurements(values=np.zeros(60), factors=balanced_factors(5, 4, 3))
        coefficients = _coefficients(_design(data))
        assert np.allclose(np.tril(coefficients, k=-1), 0.0)


class TestTheUnbalancedExpectedSumsOfSquares:
    """The claim no published table covers, checked by simulating the model."""

    def test_the_coefficients_predict_the_simulated_expectations(self) -> None:
        """Average SS over many draws must match the coefficient matrix's prediction.

        This is the test that would catch a wrong unbalanced coefficient. A
        design-dependent error would leave the balanced checks above passing and
        every published example intact, and would quietly misattribute variance
        on exactly the ragged sampling real fab data has.
        """
        factors = ragged_factors()
        truth = Truth(3.0, 2.0, 1.0)
        replications = 3000
        generator = np.random.default_rng(0)

        totals = np.zeros(3)
        for _ in range(replications):
            values = draw_on(factors, truth, generator)
            data = NestedMeasurements(values=values, factors=factors)
            totals += [term.sum_of_squares for term in _table(_design(data), LOT_WAFER_SITE_MODEL)]
        simulated = totals / replications

        design = _design(NestedMeasurements(values=np.zeros(factors.shape[1]), factors=factors))
        predicted = _coefficients(design) @ truth.variances

        assert simulated == pytest.approx(predicted[1:], rel=0.03)

    def test_the_design_is_genuinely_unbalanced(self) -> None:
        """Guard on the test above: it proves nothing about a design that is balanced."""
        factors = ragged_factors()
        values = draw_on(factors, Truth(3.0, 2.0, 1.0), np.random.default_rng(2))
        assert not decompose_variance(NestedMeasurements(values=values, factors=factors)).balanced

    def test_a_balanced_design_is_reported_as_balanced(self) -> None:
        """The flag has to distinguish the two, or reporting it is pointless."""
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (6, 4, 3))
        data = NestedMeasurements(values=values, factors=balanced_factors(6, 4, 3))
        assert decompose_variance(data).balanced


class TestTheComponentsRecoverKnownTruth:
    """Components chosen, then estimated, then compared."""

    @pytest.mark.parametrize(
        ("level", "expected"),
        [("lot", 3.0), ("wafer", 2.0), ("site", 1.0)],
    )
    def test_each_component_is_recovered_on_a_balanced_hierarchy(
        self, level: str, expected: float
    ) -> None:
        """Tolerances widen as the level moves outward, because n falls with it."""
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (200, 5, 4), seed=3)
        data = NestedMeasurements(values=values, factors=balanced_factors(200, 5, 4))
        result = decompose_variance(data)
        assert np.sqrt(result.variance_of(level)) == pytest.approx(expected, rel=0.12)

    def test_the_components_are_recovered_on_a_ragged_hierarchy(self) -> None:
        """Unbalanced estimates are less precise but must not be biased."""
        factors = ragged_factors()
        generator = np.random.default_rng(7)
        truth = Truth(3.0, 2.0, 1.0)
        estimates = np.array(
            [
                [
                    decompose_variance(
                        NestedMeasurements(
                            values=draw_on(factors, truth, generator), factors=factors
                        )
                    ).variance_of(level)
                    for level in ("lot", "wafer", "site")
                ]
                for _ in range(400)
            ]
        )
        assert np.sqrt(estimates.mean(axis=0)) == pytest.approx([3.0, 2.0, 1.0], rel=0.06)

    def test_the_dominant_component_is_identified(self) -> None:
        """Which level to investigate first is the question this module answers."""
        values = simulate_balanced(Truth(0.5, 4.0, 0.5), (60, 5, 4), seed=2)
        data = NestedMeasurements(values=values, factors=balanced_factors(60, 5, 4))
        assert decompose_variance(data).dominant == "wafer"

    def test_a_deeper_hierarchy_is_decomposed_the_same_way(self) -> None:
        """Tool above lot is the decomposition an investigation actually wants.

        Nothing about the estimator changes with depth, which is the point of
        not fixing it at three.
        """
        generator = np.random.default_rng(4)
        tools, lots, wafers, sites = 4, 12, 4, 3
        tool_effect = generator.normal(0.0, 4.0, (tools, 1, 1, 1))
        lot_effect = generator.normal(0.0, 3.0, (tools, lots, 1, 1))
        wafer_effect = generator.normal(0.0, 2.0, (tools, lots, wafers, 1))
        site_effect = generator.normal(0.0, 1.0, (tools, lots, wafers, sites))
        values = (100.0 + tool_effect + lot_effect + wafer_effect + site_effect).ravel()

        per_tool = lots * wafers * sites
        factors = np.vstack(
            [
                np.repeat(np.arange(tools), per_tool),
                np.tile(np.repeat(np.arange(lots), wafers * sites), tools),
                np.tile(np.repeat(np.arange(wafers), sites), tools * lots),
            ]
        )
        model = VarianceModel(levels=("tool", "lot", "wafer"), residual="site")
        result = decompose_variance(NestedMeasurements(values=values, factors=factors), model)

        assert result.model.names == ("tool", "lot", "wafer", "site")
        assert np.sqrt(result.variance_of("site")) == pytest.approx(1.0, rel=0.1)
        assert np.sqrt(result.variance_of("wafer")) == pytest.approx(2.0, rel=0.15)
        assert result.dominant in {"tool", "lot"}


class TestNestingIsByPathNotByLabel:
    """A slot number repeats in every lot, and must not be read as one wafer."""

    def test_repeated_child_codes_are_not_pooled_across_parents(self) -> None:
        """Wafer codes restarting each lot give the same answer as globally unique ones."""
        lots, wafers, sites = 15, 4, 3
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (lots, wafers, sites), seed=8)
        repeated = balanced_factors(lots, wafers, sites)
        unique = np.vstack([repeated[0], repeated[0] * wafers + repeated[1]])

        by_slot = decompose_variance(NestedMeasurements(values=values, factors=repeated))
        by_identity = decompose_variance(NestedMeasurements(values=values, factors=unique))

        for level in ("lot", "wafer", "site"):
            assert by_slot.variance_of(level) == pytest.approx(by_identity.variance_of(level))

    def test_pooling_by_label_would_have_changed_the_answer(self) -> None:
        """Guard on the test above: it is only meaningful if the two differ in principle.

        Crossing the design instead of nesting it is modelled here by shuffling
        which lot each observation belongs to while leaving the slot codes
        alone. The wafer component moves, which is what confirms the identity
        of a cell is doing real work rather than being incidental.
        """
        lots, wafers, sites = 15, 4, 3
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (lots, wafers, sites), seed=8)
        factors = balanced_factors(lots, wafers, sites)
        scrambled = np.vstack([np.random.default_rng(0).permutation(factors[0]), factors[1]])

        nested = decompose_variance(NestedMeasurements(values=values, factors=factors))
        crossed = decompose_variance(NestedMeasurements(values=values, factors=scrambled))
        assert nested.variance_of("wafer") != pytest.approx(crossed.variance_of("wafer"), rel=0.05)


class TestTheResultIsSelfDescribing:
    """A component labelled "wafer" means nothing without the rest of the record."""

    def test_the_method_is_named(self) -> None:
        """Two decompositions cannot be reconciled without knowing how each was fitted."""
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (6, 4, 3))
        data = NestedMeasurements(values=values, factors=balanced_factors(6, 4, 3))
        assert decompose_variance(data).method == HENDERSON_METHOD_I

    def test_the_model_travels_with_the_result(self) -> None:
        """The hierarchy is part of the finding, not context the caller must remember."""
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (6, 4, 3))
        data = NestedMeasurements(values=values, factors=balanced_factors(6, 4, 3))
        result = decompose_variance(data)
        assert result.model == LOT_WAFER_SITE_MODEL
        assert result.n_observations == 6 * 4 * 3

    def test_the_cell_counts_are_reported(self) -> None:
        """How many lots an estimate rests on is what says whether to believe it."""
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (6, 4, 3))
        data = NestedMeasurements(values=values, factors=balanced_factors(6, 4, 3))
        counts = {term.name: term.n_cells for term in decompose_variance(data).table}
        assert counts == {"lot": 6, "wafer": 24, "site": 72}

    def test_an_unknown_level_is_refused_rather_than_reported_as_zero(self) -> None:
        """Zero would be indistinguishable from a component that was resolved as absent."""
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (6, 4, 3))
        data = NestedMeasurements(values=values, factors=balanced_factors(6, 4, 3))
        with pytest.raises(ConfigurationError, match="no such level"):
            decompose_variance(data).variance_of("chamber")


class TestTheRefusals:
    """What the module declines to answer, and why."""

    def test_one_wafer_per_lot_is_refused(self) -> None:
        """There is no wafer-to-wafer variation to estimate, and none can be invented."""
        values = simulate_balanced(Truth(3.0, 0.0, 1.0), (10, 1, 4))
        data = NestedMeasurements(values=values, factors=balanced_factors(10, 1, 4))
        with pytest.raises(InsufficientDataError, match="wafer"):
            decompose_variance(data)

    def test_one_measurement_per_wafer_is_refused(self) -> None:
        """Without a repeat within a wafer the residual has no degrees of freedom."""
        values = simulate_balanced(Truth(3.0, 2.0, 0.0), (10, 4, 1))
        data = NestedMeasurements(values=values, factors=balanced_factors(10, 4, 1))
        with pytest.raises(InsufficientDataError, match="site"):
            decompose_variance(data)

    def test_a_single_lot_is_refused(self) -> None:
        """One lot cannot exhibit lot-to-lot variation."""
        values = simulate_balanced(Truth(0.0, 2.0, 1.0), (1, 4, 3))
        data = NestedMeasurements(values=values, factors=balanced_factors(1, 4, 3))
        with pytest.raises(InsufficientDataError, match="lot"):
            decompose_variance(data)

    def test_identical_measurements_are_refused(self) -> None:
        """There is no variation to apportion, so every share would be zero over zero."""
        data = NestedMeasurements(values=np.full(60, 42.0), factors=balanced_factors(5, 4, 3))
        with pytest.raises(DegenerateSeriesError):
            decompose_variance(data)

    def test_a_model_of_the_wrong_depth_is_refused(self) -> None:
        """Silently ignoring a supplied level would mislabel every component below it."""
        values = simulate_balanced(Truth(3.0, 2.0, 1.0), (6, 4, 3))
        data = NestedMeasurements(values=values, factors=balanced_factors(6, 4, 3))
        model = VarianceModel(levels=("tool", "lot", "wafer"), residual="site")
        with pytest.raises(ConfigurationError, match="different hierarchies"):
            decompose_variance(data, model)

    def test_misaligned_codes_are_refused(self) -> None:
        """A code per observation, or the decomposition is of some other data."""
        with pytest.raises(ConfigurationError, match="every observation"):
            NestedMeasurements(values=np.zeros(60), factors=balanced_factors(5, 4, 2))

    def test_a_model_without_levels_is_refused(self) -> None:
        """With no grouping factor the answer is the sample variance, computed elsewhere."""
        with pytest.raises(ConfigurationError, match="at least one grouping factor"):
            VarianceModel(levels=(), residual="site")

    def test_a_repeated_level_name_is_refused(self) -> None:
        """Two components with one name cannot be told apart in the report."""
        with pytest.raises(ConfigurationError, match="distinct name"):
            VarianceModel(levels=("lot", "lot"), residual="site")
