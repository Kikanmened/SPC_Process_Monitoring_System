"""Classify a wafer field as radial, edge, asymmetric, or none (FR-S02).

``none`` is the default outcome, not the residual. A classifier obliged to
choose among three patterns will invent one in noise — the detection-side
analogue of the rendering failure recorded as R-43 — so the vocabulary has to
let it say there is no signature at all.

Edge is nested inside radial geometrically: the outer sites are also the ones
with the largest radius, so a raw correlation contest lets a bowl beat a ring.
The decision rule therefore asks about edge structure *in the radial residuals*
before it awards a radial label. That ordering is physical, not a tie-break.

The three statistics use geometric predictors that do not share code or
parameters with the synthetic generator's profile functions (ADR-0021).
"""

from __future__ import annotations

from dataclasses import dataclass

from spc_platform.analytics.spatial.asymmetry import asymmetry_score
from spc_platform.analytics.spatial.edge import edge_score
from spc_platform.analytics.spatial.field import WaferField
from spc_platform.analytics.spatial.radial import radial_score
from spc_platform.domain.enums import SpatialSignature

DEFAULT_MINIMUM_SCORE = 0.75
"""Correlation below which a pattern cannot win.

On a thirteen-site plan this keeps the false-positive rate on unstructured
wafers around one percent, while a signature whose amplitude is a few times
the site noise still clears the bar. Nine-site plans are accepted but noisier;
five-site plans are refused at construction.
"""

_ASYMMETRY_MARGIN = 0.05
"""How far ahead of the radial score an asymmetric tilt must be.

A weak tilt on top of a bowl should not steal the radial label.
"""


@dataclass(frozen=True, slots=True)
class SignaturePolicy:
    """Thresholds that turn three scores into one classification.

    Attributes
    ----------
    minimum_score
        Correlation a pattern must reach before it can win.
    asymmetry_margin
        Lead an asymmetric score must hold over the radial score.
    """

    minimum_score: float = DEFAULT_MINIMUM_SCORE
    asymmetry_margin: float = _ASYMMETRY_MARGIN


@dataclass(frozen=True, slots=True)
class SignatureClassification:
    """The outcome of classifying one wafer field.

    Attributes
    ----------
    signature
        The chosen class, including ``none``.
    statistic
        The score that decided the class.
    threshold
        The policy minimum the winner had to clear.
    scores
        All three pattern scores, so a caller can see the near-misses.
    sites_used
        How many sites entered the classification.
    """

    signature: SpatialSignature
    statistic: float
    threshold: float
    scores: dict[SpatialSignature, float]
    sites_used: int


def classify_spatial_signature(
    field: WaferField,
    policy: SignaturePolicy | None = None,
) -> SignatureClassification:
    """Classify a wafer field as radial, edge, asymmetric, or none.

    Parameters
    ----------
    field
        Site coordinates and values on one wafer.
    policy
        Score thresholds. Defaults to :data:`DEFAULT_MINIMUM_SCORE`.

    Returns
    -------
    SignatureClassification
        Always includes a class — ``none`` when nothing clears the threshold.

    Raises
    ------
    InsufficientSitesError
        If the field has fewer sites than a signature needs.
    """
    active = policy if policy is not None else SignaturePolicy()
    scores = {
        SpatialSignature.RADIAL: radial_score(field),
        SpatialSignature.EDGE: edge_score(field),
        SpatialSignature.ASYMMETRIC: asymmetry_score(field),
    }

    asymmetric = scores[SpatialSignature.ASYMMETRIC]
    edge = scores[SpatialSignature.EDGE]
    radial = scores[SpatialSignature.RADIAL]

    if (
        asymmetric >= active.minimum_score
        and asymmetric >= radial + active.asymmetry_margin
        and asymmetric >= edge
    ):
        chosen, statistic = SpatialSignature.ASYMMETRIC, asymmetric
    elif edge >= active.minimum_score:
        # Edge structure in the radial residuals takes precedence over a raw
        # radial correlation: a ring is not a bowl, even when the bowl fit is
        # numerically close.
        chosen, statistic = SpatialSignature.EDGE, edge
    elif radial >= active.minimum_score:
        chosen, statistic = SpatialSignature.RADIAL, radial
    else:
        chosen, statistic = SpatialSignature.NONE, max(scores.values())

    return SignatureClassification(
        signature=chosen,
        statistic=statistic,
        threshold=active.minimum_score,
        scores=scores,
        sites_used=field.n_sites,
    )
