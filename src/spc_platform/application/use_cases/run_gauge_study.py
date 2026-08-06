"""Run a crossed gauge R&R study and judge acceptance (FR-M01 - FR-M03)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from spc_platform.analytics.msa import (
    AcceptanceBands,
    GaugeJudgement,
    GaugeRRResult,
    GaugeStudy,
    gauge_rr_anova,
    judge,
)
from spc_platform.application.audit import AuditEventType
from spc_platform.application.context import ApplicationServices
from spc_platform.application.ports.authorisation import ProtectedAction
from spc_platform.application.use_cases._audit import write_audit
from spc_platform.common.types import FloatArray
from spc_platform.domain.ids import ActorId


@dataclass(frozen=True, slots=True)
class GaugeStudyOutcome:
    """ANOVA result plus configured judgement."""

    result: GaugeRRResult
    judgement: GaugeJudgement


def run_gauge_study(  # noqa: PLR0913 — use-case boundary parameters
    services: ApplicationServices,
    *,
    actor: ActorId,
    measurements: FloatArray,
    bands: AcceptanceBands,
    tolerance: float | None = None,
    reason: str = "",
) -> GaugeStudyOutcome:
    """Analyse a balanced crossed study payload and audit the outcome.

    Study design is supplied by the caller for v1 (no gauge-study repository).
    ``measurements`` must be shape ``(parts, operators, replicates)``.
    """
    services.auth.require(actor, ProtectedAction.RUN_GAUGE_STUDY)
    array = np.asarray(measurements, dtype=np.float64)
    study = GaugeStudy(measurements=array, tolerance=tolerance)
    result = gauge_rr_anova(study)
    judgement = judge(result, bands)
    write_audit(
        services,
        event_type=AuditEventType.REPORT_GENERATED,
        actor=actor,
        reason=reason or "gauge R&R study",
        after={
            "percent_grr_study": result.percent_study_variation,
            "percent_grr_tolerance": result.percent_tolerance,
            "ndc": result.number_of_distinct_categories,
            "verdict": judgement.verdict.value,
            "deciding_criterion": judgement.deciding_criterion.value,
        },
    )
    return GaugeStudyOutcome(result=result, judgement=judgement)
