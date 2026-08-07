"""Capability screen with estimator, n, and window (NFR-U04)."""

from __future__ import annotations

from datetime import datetime

import streamlit as st
from dashboard.components.refusal_panel import refusal_markdown
from dashboard.components.statistic_label import format_statistic
from dashboard.layouts.page import page_header
from dashboard.state.session import default_actor, ensure_bundle

from spc_platform.application.use_cases import generate_capability_report
from spc_platform.common.errors import SPCPlatformError, UnstableProcessError
from spc_platform.domain.ids import ParameterId, ProductId

page_header(
    "Capability",
    "Cp/Cpk/Pp/Ppk only when the process is in control (FR-P04).",
)

bundle = ensure_bundle(st.session_state)  # type: ignore[arg-type]
parameter_id = st.text_input("Parameter", value="OXIDE_THK")
product_id = st.text_input("Product", value="DEV-A")
window_start = st.text_input("Window start (ISO)", value="2025-07-01T00:00:00+00:00")
window_end = st.text_input("Window end (ISO)", value="2025-07-14T00:00:00+00:00")

if st.button("Generate report", type="primary"):
    try:
        outcome = generate_capability_report(
            bundle.services,
            actor=default_actor(),
            parameter_id=ParameterId(parameter_id),
            product_id=ProductId(product_id),
            window_start=datetime.fromisoformat(window_start),
            window_end=datetime.fromisoformat(window_end),
        )
    except UnstableProcessError as exc:
        st.markdown(
            refusal_markdown(
                "Capability refused",
                f"Process not in control (FR-P04). {exc}",
            )
        )
    except SPCPlatformError as exc:
        st.markdown(refusal_markdown("Capability unavailable", str(exc)))
    else:
        if outcome.result is None:
            st.markdown(
                refusal_markdown(
                    "Capability refused",
                    outcome.refusal_reason or "no result returned",
                )
            )
        else:
            result = outcome.result
            st.markdown(
                format_statistic(
                    "Cpk",
                    result.within.cpk,
                    n=result.n_observations,
                    window_start=result.window_start,
                    window_end=result.window_end,
                    estimator=result.within.estimator.value,
                )
            )
            st.markdown(
                format_statistic(
                    "Cp",
                    result.within.cp,
                    n=result.n_observations,
                    window_start=result.window_start,
                    window_end=result.window_end,
                    estimator=result.within.estimator.value,
                )
            )
            st.markdown(
                format_statistic(
                    "Ppk",
                    result.overall.cpk,
                    n=result.n_observations,
                    window_start=result.window_start,
                    window_end=result.window_end,
                    estimator=result.overall.estimator.value,
                )
            )
            st.caption(f"Stability: {result.stability.value}")
