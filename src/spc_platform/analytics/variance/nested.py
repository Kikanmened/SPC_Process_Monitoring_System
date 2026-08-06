r"""Nested variance decomposition (FR-S07, BO-5).

A wafer parameter that looks marginally capable is not one problem. It is
site-to-site non-uniformity, or wafer-to-wafer drift within a lot, or lot-to-lot
mismatch, and the three have different owners and different fixes. Chamber
uniformity work will not help a lot-to-lot problem, and requalifying incoming
material will not flatten a within-wafer profile. Reporting one total sigma
tells an engineer that something is wrong and nothing about where to look;
splitting it is the single most useful piece of evidence this platform produces
about a continuous parameter.

The model is fully nested and fully random:

.. math::
    y_{ijk} = \mu + L_i + W_{j(i)} + \varepsilon_{k(ij)}

with each term a draw from a population rather than a level of interest in its
own right. That is the correct reading of fab data — this lot is not
interesting, the spread of lots is — and it is what makes the components
variances rather than effects.

Four things here are deliberate.

**Unbalanced designs are supported directly.** Real sampling is not balanced:
a lot gets five wafers measured, the next gets two, one wafer gets a re-measure.
The expected mean squares therefore carry design-dependent coefficients rather
than the textbook ``n`` and ``bn`` (Searle, Casella and McCulloch §4.3). The
balanced case falls out of the same arithmetic unchanged, so there is one code
path and no silent switch between two estimators.

**Nesting is by path, not by label.** Slot 7 in lot A and slot 7 in lot B are
different wafers. Treating the slot number as a global identifier would cross
the design instead of nesting it, and would quietly reattribute wafer-to-wafer
variation to a "slot effect" that the analysis was never asked about. Cells are
identified by the whole chain of codes above them.

**The depth is not fixed at three.** Lot, wafer, site is the common case, but
tool above lot is the same computation and is exactly the decomposition needed
when a fleet is suspected. Fixing the depth would have meant a second
implementation for the case that matters most in an investigation.

**Negative components are clamped and the clamp is recorded**, for the same
reason as in the gauge study: the estimators are differences of mean squares,
so a component near zero comes out negative about half the time, and "not
resolved" must not be reported as "absent".

References
----------
Searle, S. R., Casella, G. and McCulloch, C. E. (1992). *Variance Components*,
Wiley, §4.3 (unbalanced nested classifications, Henderson's Method I).
Montgomery, D. C. (2020). *Design and Analysis of Experiments*, 10th ed.,
§14.1 (the two-stage nested design), §14.1.3 (expected mean squares).
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §5.5 (rational subgrouping and the components it separates).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spc_platform.common.errors import (
    ConfigurationError,
    DegenerateSeriesError,
    InsufficientDataError,
)
from spc_platform.common.types import FloatArray, IntArray

MIN_LEVELS = 1
"""One grouping factor plus the residual is the smallest decomposition there is.

With no factor at all there is nothing to apportion — the answer would be the
sample variance, which does not need this module.
"""

LOT_WAFER_SITE: tuple[str, str, str] = ("lot", "wafer", "site")
"""The conventional fab hierarchy, outermost first (FR-S07).

Named here so that the two callers that want the standard decomposition agree
about what the residual is called. ``site`` is the residual: within-wafer
variation is what is left after lot and wafer means are removed, which is the
same thing as site-to-site spread only when each site is measured once.
"""


@dataclass(frozen=True, slots=True)
class VarianceModel:
    """The hierarchy being fitted, named so a result can be read without the caller.

    Attributes
    ----------
    levels
        Grouping factors, outermost first — ``("lot", "wafer")`` for the
        classic fab hierarchy. Each must be nested within the one before it.
    residual
        What variation within the innermost cell is called. For lot and wafer
        levels this is ``"site"``: the within-wafer term.

    Raises
    ------
    ConfigurationError
        If there are no levels, or a name is repeated. A repeated name would
        make the reported decomposition ambiguous about which term is which.
    """

    levels: tuple[str, ...]
    residual: str

    def __post_init__(self) -> None:
        """Reject a hierarchy whose components could not be told apart."""
        if len(self.levels) < MIN_LEVELS:
            raise ConfigurationError(
                "a nested decomposition needs at least one grouping factor",
                levels=self.levels,
            )
        names = (*self.levels, self.residual)
        if len(set(names)) != len(names):
            raise ConfigurationError(
                "every level in the hierarchy must have a distinct name",
                names=names,
            )

    @property
    def names(self) -> tuple[str, ...]:
        """Every component's name, outermost first, residual last."""
        return (*self.levels, self.residual)

    @property
    def depth(self) -> int:
        """Grouping factors, excluding the residual."""
        return len(self.levels)


LOT_WAFER_SITE_MODEL = VarianceModel(levels=LOT_WAFER_SITE[:2], residual=LOT_WAFER_SITE[2])
"""Lot, wafer, and within-wafer — the decomposition FR-S07 names."""


@dataclass(frozen=True, slots=True)
class NestedMeasurements:
    """Measurements with the hierarchy they were taken under.

    Attributes
    ----------
    values
        One measurement per observation.
    factors
        Shape ``(levels, observations)``, integer codes, outermost level first.
        Codes need only be unique *within their parent*: slot numbers repeating
        in every lot is the expected input, not an error, because cells are
        identified by the whole path rather than by the code alone.

    Raises
    ------
    ConfigurationError
        If the shapes disagree, which would silently misalign observations with
        their groups and produce a plausible, wrong decomposition.
    """

    values: FloatArray
    factors: IntArray

    def __post_init__(self) -> None:
        """Reject inputs whose shapes cannot describe the same observations."""
        expected_factor_dimensions = 2
        if self.values.ndim != 1:
            raise ConfigurationError(
                "measurements are one per observation",
                shape=self.values.shape,
            )
        if self.factors.ndim != expected_factor_dimensions:
            raise ConfigurationError(
                "factors are indexed by level and observation",
                shape=self.factors.shape,
            )
        if self.factors.shape[1] != self.values.shape[0]:
            raise ConfigurationError(
                "every observation needs a code at every level",
                n_observations=int(self.values.shape[0]),
                n_coded=int(self.factors.shape[1]),
            )

    @property
    def n_observations(self) -> int:
        """Measurements in the study."""
        return int(self.values.shape[0])

    @property
    def depth(self) -> int:
        """Grouping factors supplied."""
        return int(self.factors.shape[0])


@dataclass(frozen=True, slots=True)
class NestedTerm:
    """One row of the nested ANOVA table.

    Attributes
    ----------
    name
        The level this row is for, from the model.
    sum_of_squares, degrees_of_freedom, mean_square
        The decomposition. Degrees of freedom are cells at this level minus
        cells at the level above, which reduces to the familiar ``a - 1`` and
        ``a(b - 1)`` when the design is balanced.
    n_cells
        Distinct groups at this level — lots, then wafers within lots. The
        figure that says how much the estimate can be trusted, and the one
        most often missing from a variance report.
    """

    name: str
    sum_of_squares: float
    degrees_of_freedom: int
    mean_square: float
    n_cells: int


@dataclass(frozen=True, slots=True)
class NestedComponent:
    """One estimated variance component.

    Attributes
    ----------
    name
        The level, from the model.
    variance
        The component, in squared measurement units. Zero if it was clamped.
    clamped
        Whether the raw estimate was negative and set to zero. A clamped
        component means the design could not resolve it — read it as unknown
        and small, not as absent.
    """

    name: str
    variance: float
    clamped: bool

    @property
    def standard_deviation(self) -> float:
        """The component on the measurement's own scale, which is how it is read."""
        return float(np.sqrt(self.variance))


@dataclass(frozen=True, slots=True)
class NestedVarianceResult:
    """The decomposition, with the model and method named (BO-5).

    Attributes
    ----------
    model
        The hierarchy that was fitted. Reported because a component labelled
        "wafer" means nothing without knowing what sat above it.
    components
        One per level, outermost first, residual last.
    table
        The ANOVA rows the components were derived from, for audit.
    method
        How the components were estimated, so two results can be compared.
    balanced
        Whether every cell had the same number of children. Unbalanced
        estimates are still unbiased but are less precise, and the caller
        should know which it has.
    n_observations
        Measurements the decomposition rests on.
    """

    model: VarianceModel
    components: tuple[NestedComponent, ...]
    table: tuple[NestedTerm, ...]
    method: str
    balanced: bool
    n_observations: int

    @property
    def total(self) -> float:
        """Total variance, the components being independent by construction."""
        return float(sum(component.variance for component in self.components))

    def variance_of(self, name: str) -> float:
        """Return one component by name.

        Parameters
        ----------
        name
            A level name from the model.

        Raises
        ------
        ConfigurationError
            If the name is not in the model, rather than returning zero — a
            zero would be indistinguishable from a resolved absence of effect.
        """
        for component in self.components:
            if component.name == name:
                return component.variance
        raise ConfigurationError(
            "no such level in this decomposition",
            requested=name,
            available=self.model.names,
        )

    def percent_of(self, name: str) -> float:
        """Return one component's share of the total variance, as a percentage.

        On variances rather than standard deviations, because shares must add
        to one hundred and shares of standard deviations do not. The gauge
        study's %GRR uses the opposite convention for the opposite reason: it
        compares one quantity against another rather than partitioning a whole.
        """
        total = self.total
        if total <= 0.0:  # pragma: no cover - guarded by the degenerate check
            return 0.0
        return 100.0 * self.variance_of(name) / total

    @property
    def dominant(self) -> str:
        """The largest component's name — where an investigation should start."""
        return max(self.components, key=lambda component: component.variance).name


HENDERSON_METHOD_I = "henderson-i-nested-anova"
"""Analysis of variance with expected mean squares inverted for the components.

Named on the result because it is not the only defensible choice. Restricted
maximum likelihood would give different figures on a badly unbalanced design,
and a report that does not say which was used cannot be reconciled with one
that used the other.
"""


def decompose_variance(
    data: NestedMeasurements,
    model: VarianceModel = LOT_WAFER_SITE_MODEL,
) -> NestedVarianceResult:
    r"""Split total variation into the levels of a nested hierarchy.

    The sums of squares are the usual nested ones, each level measured against
    the cell above it:

    .. math::
        SS_\ell = \sum_{c \,\in\, \text{level } \ell} n_c
                  (\bar y_c - \bar y_{\mathrm{parent}(c)})^2

    What is not usual is the inversion. For unbalanced data the expected mean
    squares are

    .. math::
        E[SS_\ell] = \sum_{m \ge \ell} k_{\ell m} \sigma^2_m, \qquad
        k_{\ell m} = \sum_{c \,\in\, m} \frac{n_c^2}{n_{A(c,\ell)}}
                   - \sum_{c \,\in\, m} \frac{n_c^2}{n_{A(c,\ell-1)}}

    with :math:`A(c,\ell)` the ancestor of cell :math:`c` at level
    :math:`\ell`. The matrix is triangular, so the components come out by back
    substitution from the residual upward. On balanced data
    :math:`k_{\ell m}` collapses to the textbook coefficients — :math:`bn` for
    the lot term, :math:`n` for the wafer term — so this reproduces the
    familiar result exactly rather than approximating it.

    Parameters
    ----------
    data
        Measurements and their group codes, outermost level first.
    model
        The hierarchy being fitted. Defaults to lot, wafer, and within-wafer.

    Returns
    -------
    NestedVarianceResult
        A component per level, the table behind it, and the method used.

    Raises
    ------
    ConfigurationError
        If the model and the supplied codes describe different hierarchies.
    InsufficientDataError
        If a level has no degrees of freedom — one wafer per lot leaves
        nothing to estimate wafer-to-wafer variation from, and no arithmetic
        will recover it. Refused rather than reported as zero.
    DegenerateSeriesError
        If every measurement is identical, so there is no variation to split.

    References
    ----------
    Searle, Casella and McCulloch (1992), *Variance Components*, §4.3.
    Montgomery (2020), *Design and Analysis of Experiments*, 10th ed., §14.1.
    """
    if data.depth != model.depth:
        raise ConfigurationError(
            "the model and the supplied codes describe different hierarchies",
            model_levels=model.levels,
            coded_levels=data.depth,
        )
    if float(np.ptp(data.values)) <= 0.0:
        raise DegenerateSeriesError(
            "every measurement is identical, so no variation can be apportioned",
            n=data.n_observations,
        )

    design = _design(data)
    _require_estimable(design, model)
    table = _table(design, model)
    components = _components(design, table, model)
    return NestedVarianceResult(
        model=model,
        components=components,
        table=table,
        method=HENDERSON_METHOD_I,
        balanced=design.balanced,
        n_observations=data.n_observations,
    )


@dataclass(frozen=True, slots=True)
class _Design:
    """The cell structure, resolved once and reused by every later step.

    Indexed by level, where level 0 is the grand mean, levels 1 to ``depth``
    are the grouping factors, and the last level is the residual, whose cells
    are the individual observations. Carrying the grand mean and the residual
    as levels in their own right is what lets one loop cover terms that would
    otherwise each need their own special case.

    Attributes
    ----------
    codes
        Per level, the cell each observation belongs to.
    sizes
        Per level, the number of observations in each cell.
    means
        Per level, each cell's mean.
    ancestors
        ``ancestors[m][l]`` gives, for each cell at level ``m``, the index of
        its ancestor cell at level ``l``.
    """

    codes: tuple[IntArray, ...]
    sizes: tuple[IntArray, ...]
    means: tuple[FloatArray, ...]
    ancestors: tuple[tuple[IntArray, ...], ...]

    @property
    def n_levels(self) -> int:
        """Levels including the grand mean and the residual."""
        return len(self.codes)

    @property
    def balanced(self) -> bool:
        """Whether every cell at every level holds the same number of observations."""
        return all(bool(np.all(size == size[0])) for size in self.sizes[1:])


def _design(data: NestedMeasurements) -> _Design:
    """Resolve the cell structure, identifying cells by path rather than by label.

    A cell at level ``l`` is a distinct combination of the codes at levels 1 to
    ``l``, so a wafer is (lot, slot) and not slot. Getting this wrong would
    cross the design instead of nesting it and would reattribute variation
    between levels without failing.
    """
    values = data.values
    n = data.n_observations
    grand = np.zeros(n, dtype=np.int_)

    codes: list[IntArray] = [grand]
    representatives: list[IntArray] = [np.zeros(1, dtype=np.int_)]
    for level in range(1, data.depth + 1):
        paths = np.ascontiguousarray(data.factors[:level].T)
        _, first, inverse = np.unique(paths, axis=0, return_index=True, return_inverse=True)
        codes.append(np.asarray(inverse, dtype=np.int_).reshape(n))
        representatives.append(np.asarray(first, dtype=np.int_))
    codes.append(np.arange(n, dtype=np.int_))
    representatives.append(np.arange(n, dtype=np.int_))

    sizes = tuple(np.bincount(code).astype(np.int_) for code in codes)
    means = tuple(
        np.bincount(code, weights=values).astype(np.float64) / size
        for code, size in zip(codes, sizes, strict=True)
    )
    ancestors = tuple(
        tuple(codes[above][representatives[level]] for above in range(len(codes)))
        for level in range(len(codes))
    )
    return _Design(codes=tuple(codes), sizes=sizes, means=means, ancestors=ancestors)


def _require_estimable(design: _Design, model: VarianceModel) -> None:
    """Refuse a design in which some named component does not exist.

    Raises
    ------
    InsufficientDataError
        If a level contributes no degrees of freedom. One wafer per lot, or
        one measurement per wafer, means the corresponding component is not
        estimable at all — reporting zero would be a fabrication.
    """
    for level, name in enumerate(model.names, start=1):
        cells = len(design.sizes[level])
        above = len(design.sizes[level - 1])
        if cells <= above:
            parent = "the study" if level == 1 else f"every {model.names[level - 2]}"
            raise InsufficientDataError(
                f"{parent} holds one {name}, so the {name} component has no "
                "degrees of freedom and is not estimable from this design",
                level=name,
                n_cells=cells,
                n_parents=above,
            )


def _table(design: _Design, model: VarianceModel) -> tuple[NestedTerm, ...]:
    """Build one ANOVA row per level, each measured against the cell above it."""
    rows: list[NestedTerm] = []
    for level, name in enumerate(model.names, start=1):
        sizes = design.sizes[level]
        parents = design.ancestors[level][level - 1]
        deviations = design.means[level] - design.means[level - 1][parents]
        sum_of_squares = float(np.sum(sizes * deviations**2))
        degrees = len(sizes) - len(design.sizes[level - 1])
        rows.append(
            NestedTerm(
                name=name,
                sum_of_squares=sum_of_squares,
                degrees_of_freedom=degrees,
                mean_square=sum_of_squares / degrees,
                n_cells=len(sizes),
            )
        )
    return tuple(rows)


def _coefficients(design: _Design) -> FloatArray:
    r"""Build the expected sum of squares coefficients for a possibly unbalanced hierarchy.

    Entry ``(l, m)`` is the multiplier on :math:`\sigma^2_m` in
    :math:`E[SS_l]`, following Searle, Casella and McCulloch §4.3. The matrix
    is upper triangular because a level's sum of squares cannot contain
    variation from a level above it.
    """
    levels = design.n_levels
    matrix = np.zeros((levels, levels), dtype=np.float64)
    for outer in range(1, levels):
        for inner in range(outer, levels):
            squared = design.sizes[inner].astype(np.float64) ** 2
            within = design.sizes[outer][design.ancestors[inner][outer]].astype(np.float64)
            above = design.sizes[outer - 1][design.ancestors[inner][outer - 1]].astype(np.float64)
            matrix[outer, inner] = float(np.sum(squared / within) - np.sum(squared / above))
    return matrix


def _components(
    design: _Design,
    table: tuple[NestedTerm, ...],
    model: VarianceModel,
) -> tuple[NestedComponent, ...]:
    """Invert the expected mean squares by back substitution, clamping at zero.

    The residual comes out first and unchanged — its mean square estimates it
    directly — and each level above subtracts the contributions of everything
    nested inside it. Clamping happens on the way up, so a level whose raw
    estimate was negative contributes zero to the level above rather than
    inflating it.
    """
    coefficients = _coefficients(design)
    variances = np.zeros(len(table) + 1, dtype=np.float64)
    clamped: list[bool] = [False] * len(table)

    for index in range(len(table) - 1, -1, -1):
        level = index + 1
        term = table[index]
        nested = float(np.dot(coefficients[level, level + 1 :], variances[level + 1 :]))
        raw = (term.sum_of_squares - nested) / coefficients[level, level]
        clamped[index] = raw < 0.0
        variances[level] = max(0.0, raw)

    return tuple(
        NestedComponent(name=name, variance=float(variances[index + 1]), clamped=clamped[index])
        for index, name in enumerate(model.names)
    )
