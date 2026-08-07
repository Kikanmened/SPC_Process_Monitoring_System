"""Line overview ordered by what needs attention."""

from __future__ import annotations

import streamlit as st
from dashboard.layouts.page import page_header
from dashboard.state.session import default_actor, ensure_bundle

from spc_platform.application.use_cases import build_line_overview
from spc_platform.domain.ids import ParameterId

page_header(
    "Line overview",
    "Parameters ordered by open violations — worst first, not alphabetically.",
)

bundle = ensure_bundle(st.session_state)  # type: ignore[arg-type]
actor = default_actor()
overview = build_line_overview(
    bundle.services,
    actor=actor,
    parameter_ids=(ParameterId("OXIDE_THK"),),
)

st.metric("Open violations", overview.n_open_violations)
st.metric("Parameters shown", overview.n_parameters)

if not overview.rows:
    st.info("No parameters need attention in the current queue.")
else:
    for row in overview.rows:
        severity = row.highest_severity.value if row.highest_severity else "none"
        baseline = "baseline active" if row.has_active_baseline else "NO BASELINE"
        st.write(
            f"**{row.parameter_id}** — open={row.open_violations}, "
            f"severity={severity}, {baseline} (rank {row.attention_rank})"
        )
