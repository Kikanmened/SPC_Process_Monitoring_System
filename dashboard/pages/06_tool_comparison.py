"""Matched-parameter tool comparison with a named statistical test (FR-T01)."""

from __future__ import annotations

from datetime import datetime

import streamlit as st
from dashboard.components.refusal_panel import refusal_markdown
from dashboard.components.statistic_label import format_statistic
from dashboard.layouts.page import page_header
from dashboard.state.session import default_actor, ensure_bundle

from spc_platform.application.use_cases import compare_tools
from spc_platform.common.errors import SPCPlatformError
from spc_platform.domain.ids import ParameterId

page_header(
    "Tool comparison",
    "Welch's t-test on matched parameter groups. States the test — does not assert a cause.",
)

bundle = ensure_bundle(st.session_state)  # type: ignore[arg-type]
parameter_id = st.text_input("Parameter", value="OXIDE_THK")
group_by = st.selectbox("Group by", options=["tool", "chamber"], index=0)
group_a = st.text_input("Group A", value="OX-01")
group_b = st.text_input("Group B", value="OX-02")
window_start = st.text_input("Window start (ISO)", value="2025-07-01T00:00:00+00:00")
window_end = st.text_input("Window end (ISO)", value="2025-07-14T00:00:00+00:00")

if st.button("Compare", type="primary"):
    try:
        view = compare_tools(
            bundle.services,
            actor=default_actor(),
            parameter_id=ParameterId(parameter_id),
            window_start=datetime.fromisoformat(window_start),
            window_end=datetime.fromisoformat(window_end),
            group_a=group_a,
            group_b=group_b,
            group_by=group_by,
        )
    except SPCPlatformError as exc:
        st.markdown(refusal_markdown("Comparison unavailable", str(exc)))
    else:
        for group in view.groups:
            st.markdown(
                format_statistic(
                    f"{group.group_kind}={group.group_key} mean",
                    group.mean,
                    n=group.n_observations,
                    window_start=view.window_start,
                    window_end=view.window_end,
                )
            )
        st.write(f"**Test:** {view.test_name}")
        st.write(f"statistic={view.statistic} · p={view.p_value} · effect={view.effect_size}")
        st.caption(view.note)
