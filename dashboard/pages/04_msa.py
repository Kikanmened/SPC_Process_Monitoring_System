"""MSA / Gauge R&R screen — judgement from the use case only."""

from __future__ import annotations

import json

import numpy as np
import streamlit as st
from dashboard.components.refusal_panel import refusal_markdown
from dashboard.components.statistic_label import format_statistic
from dashboard.layouts.page import page_header
from dashboard.state.session import default_actor, ensure_bundle

from spc_platform.application.use_cases import run_gauge_study
from spc_platform.common.errors import SPCPlatformError
from spc_platform.common.time import SystemClock

page_header(
    "MSA / Gauge R&R",
    "ANOVA gauge study with configured acceptance bands (ADR-0017).",
)

bundle = ensure_bundle(st.session_state)  # type: ignore[arg-type]
st.caption("Paste a balanced study as JSON: [parts][operators][replicates].")
default = [
    [[10.0, 10.1, 10.0], [10.2, 10.1, 10.2], [10.0, 9.9, 10.0]],
    [[11.0, 11.1, 11.0], [11.2, 11.0, 11.1], [11.0, 10.9, 11.0]],
    [[9.0, 9.1, 9.0], [9.2, 9.1, 9.2], [9.0, 8.9, 9.0]],
    [[12.0, 12.1, 12.0], [12.2, 12.0, 12.1], [12.0, 11.9, 12.0]],
    [[10.5, 10.6, 10.5], [10.7, 10.5, 10.6], [10.5, 10.4, 10.5]],
]
payload = st.text_area("Measurements JSON", value=json.dumps(default, indent=2), height=200)
acceptable = st.number_input("Acceptable %GRR", value=10.0)
marginal = st.number_input("Marginal %GRR", value=30.0)
ndc_min = st.number_input("Minimum distinct categories", value=5, step=1)
tolerance = st.number_input("Tolerance (optional, 0 = none)", value=2.0)

if st.button("Run study", type="primary"):
    try:
        measurements = np.asarray(json.loads(payload), dtype=np.float64)
        outcome = run_gauge_study(
            bundle.services,
            actor=default_actor(),
            measurements=measurements,
            acceptable_percent=float(acceptable),
            marginal_percent=float(marginal),
            minimum_distinct_categories=int(ndc_min),
            tolerance=None if tolerance <= 0 else float(tolerance),
        )
    except (SPCPlatformError, json.JSONDecodeError, ValueError, TypeError) as exc:
        st.markdown(refusal_markdown("Gauge study unavailable", str(exc)))
    else:
        now = SystemClock().now()
        st.markdown(
            format_statistic(
                "%GRR (study variation)",
                outcome.result.percent_study_variation,
                n=outcome.result.n_parts * outcome.result.n_operators * outcome.result.n_replicates,
                window_start=now,
                window_end=now,
            )
        )
        st.write(
            f"**Verdict:** {outcome.judgement.verdict.value} "
            f"(criterion={outcome.judgement.deciding_criterion.value})"
        )
        st.write(f"NDC={outcome.result.number_of_distinct_categories}")
