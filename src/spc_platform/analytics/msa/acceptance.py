"""Turning a gauge study into a verdict (FR-M03).

The bands live here as a *value the caller supplies*, not as constants compiled
into the library. That is a deliberate constraint (ADR-0017): the widely used
10/30 percent thresholds come from a copyrighted commercial publication, and
more importantly they are an organisation's decision about acceptable risk, not
a mathematical fact. A fab measuring a parameter with a 200 nm tolerance and one
measuring a parameter with a 2 nm tolerance should not be forced to the same
threshold by an import.

What this module does own is the shape of the judgement: that it is made against
the worse of the two percentages rather than the friendlier one, that a gauge
which cannot resolve enough categories fails regardless of its percentage, and
that the verdict records which criterion decided it.

References
----------
Montgomery, D. C. (2019). *Introduction to Statistical Quality Control*,
8th ed., §8.7.
Burdick, R. K., Borror, C. M. and Montgomery, D. C. (2003). "A Review of Methods
for Measurement Systems Capability Analysis." *Journal of Quality Technology*
35(4), 342-354.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from spc_platform.analytics.msa.gauge_rr import GaugeRRResult
from spc_platform.common.errors import ConfigurationError


class GaugeVerdict(StrEnum):
    """Whether a measurement system may be used for the decisions it feeds."""

    ACCEPTABLE = "acceptable"
    MARGINAL = "marginal"
    UNACCEPTABLE = "unacceptable"


class GaugeCriterion(StrEnum):
    """Which test decided the verdict.

    Recorded because the remedy differs. A gauge failing on tolerance needs a
    better instrument; a gauge failing on study variation may simply have been
    given parts that were too alike, which is a flaw in the study rather than in
    the gauge.
    """

    STUDY_VARIATION = "study_variation"
    TOLERANCE = "tolerance"
    DISTINCT_CATEGORIES = "distinct_categories"


@dataclass(frozen=True, slots=True)
class AcceptanceBands:
    """Configured thresholds for judging a gauge study.

    Attributes
    ----------
    acceptable_percent
        At or below this %GRR the system is acceptable.
    marginal_percent
        Above ``acceptable_percent`` and at or below this, the system is
        usable with justification. Above it, it is not.
    minimum_distinct_categories
        Fewest groups the system must be able to tell apart. A system below
        this fails whatever its percentage, because a percentage compares the
        gauge to the parts it was given and this does not.

    Raises
    ------
    ConfigurationError
        If the bands are not a positive increasing pair, which would make the
        verdict depend on the order the tests happened to run in.
    """

    acceptable_percent: float
    marginal_percent: float
    minimum_distinct_categories: int

    def __post_init__(self) -> None:
        """Reject bands that would make the verdict ambiguous."""
        if not 0.0 < self.acceptable_percent < self.marginal_percent:
            raise ConfigurationError(
                "acceptance bands must be positive and increasing",
                acceptable_percent=self.acceptable_percent,
                marginal_percent=self.marginal_percent,
            )
        if self.minimum_distinct_categories < 1:
            raise ConfigurationError(
                "a measurement system must resolve at least one category",
                minimum_distinct_categories=self.minimum_distinct_categories,
            )


@dataclass(frozen=True, slots=True)
class GaugeJudgement:
    """The verdict, and enough context to argue with it.

    Attributes
    ----------
    verdict
        Acceptable, marginal, or unacceptable.
    deciding_criterion
        Which test produced the verdict — the binding constraint.
    percent_study_variation
        %GRR against total observed variation.
    percent_tolerance
        %GRR against the specification width, if a tolerance was supplied.
    number_of_distinct_categories
        Groups the system can tell apart.
    bands
        The thresholds applied, carried so the verdict can be re-derived later
        even if the configuration has since changed.
    """

    verdict: GaugeVerdict
    deciding_criterion: GaugeCriterion
    percent_study_variation: float
    percent_tolerance: float | None
    number_of_distinct_categories: int
    bands: AcceptanceBands


def judge(result: GaugeRRResult, bands: AcceptanceBands) -> GaugeJudgement:
    """Apply configured acceptance bands to a gauge study (FR-M03).

    The verdict is the worst of the three tests, not the average and not the
    first to pass. A gauge that uses 8% of the observed variation and 45% of the
    tolerance is unacceptable: it cannot sort conforming parts from
    non-conforming ones, and the flattering figure only says the parts in the
    study happened to vary a lot.

    Parameters
    ----------
    result
        A completed gauge R&R study.
    bands
        The configured thresholds. Supplied rather than assumed, because what
        counts as acceptable is an organisation's decision (ADR-0017).

    Returns
    -------
    GaugeJudgement
        The verdict, which test decided it, and the figures behind it.

    References
    ----------
    Montgomery (2019), 8th ed., §8.7. Burdick, Borror and Montgomery (2003),
    *Journal of Quality Technology* 35(4).
    """
    categories = result.number_of_distinct_categories
    percentages: list[tuple[GaugeCriterion, float]] = [
        (GaugeCriterion.STUDY_VARIATION, result.percent_study_variation)
    ]
    if result.percent_tolerance is not None:
        percentages.append((GaugeCriterion.TOLERANCE, result.percent_tolerance))

    criterion, worst = max(percentages, key=lambda pair: pair[1])
    verdict = _verdict_for(worst, bands)

    if categories < bands.minimum_distinct_categories:
        resolution = GaugeVerdict.UNACCEPTABLE
        if _severity(resolution) > _severity(verdict):
            verdict = resolution
            criterion = GaugeCriterion.DISTINCT_CATEGORIES

    return GaugeJudgement(
        verdict=verdict,
        deciding_criterion=criterion,
        percent_study_variation=result.percent_study_variation,
        percent_tolerance=result.percent_tolerance,
        number_of_distinct_categories=categories,
        bands=bands,
    )


def _verdict_for(percent: float, bands: AcceptanceBands) -> GaugeVerdict:
    """Place one percentage into its band."""
    if percent <= bands.acceptable_percent:
        return GaugeVerdict.ACCEPTABLE
    if percent <= bands.marginal_percent:
        return GaugeVerdict.MARGINAL
    return GaugeVerdict.UNACCEPTABLE


def _severity(verdict: GaugeVerdict) -> int:
    """Order verdicts so the worst one can be selected."""
    return {
        GaugeVerdict.ACCEPTABLE: 0,
        GaugeVerdict.MARGINAL: 1,
        GaugeVerdict.UNACCEPTABLE: 2,
    }[verdict]
