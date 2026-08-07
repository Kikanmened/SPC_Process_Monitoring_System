"""Control chart viewer with violation markers and distinct limit styles."""

from __future__ import annotations

from datetime import UTC, datetime

import streamlit as st
from dashboard.components.chart_figure import chart_figure
from dashboard.components.refusal_panel import refusal_markdown
from dashboard.components.statistic_label import format_statistic
from dashboard.layouts.page import page_header
from dashboard.state.session import default_actor, ensure_bundle

from spc_platform.application.use_cases import build_chart_view
from spc_platform.common.errors import SPCPlatformError
from spc_platform.domain.ids import LotId, ParameterId

page_header(
    "Control chart",
    "Phase II individuals chart. Control limits are solid; specification limits are dashed.",
)

bundle = ensure_bundle(st.session_state)  # type: ignore[arg-type]
parameter_id = st.text_input("Parameter", value="OXIDE_THK")
lot_id = st.text_input("Lot (optional)", value="LOT-DEMO")
window_start = st.text_input("Window start (ISO)", value="2025-07-01T00:00:00+00:00")
window_end = st.text_input("Window end (ISO)", value="2025-07-14T00:00:00+00:00")

if st.button("Load chart", type="primary"):
    try:
        view = build_chart_view(
            bundle.services,
            actor=default_actor(),
            parameter_id=ParameterId(parameter_id),
            window_start=datetime.fromisoformat(window_start),
            window_end=datetime.fromisoformat(window_end),
            lot_id=LotId(lot_id) if lot_id.strip() else None,
        )
    except SPCPlatformError as exc:
        st.markdown(refusal_markdown("Chart unavailable", str(exc)))
    else:
        st.plotly_chart(chart_figure(view), use_container_width=True)
        st.markdown(
            format_statistic(
                "Centre line",
                view.centre_line,
                n=view.n_observations,
                window_start=view.window_start,
                window_end=view.window_end,
                estimator=view.sigma_estimator.value,
            )
        )
        st.caption(
            f"Baseline {view.baseline_id} · data_revision={view.data_revision} · "
            f"config_revision={view.config_revision} · "
            f"UCL={view.ucl:.4g} LCL={view.lcl:.4g} (control) · "
            f"USL={view.specification_usl} LSL={view.specification_lsl} (spec)"
        )
        violations = [point for point in view.points if point.violated]
        if violations:
            st.subheader("Violations (shape + label)")
            for point in violations:
                st.write(
                    f"OOC @ index {point.index}: rules={list(point.rule_ids)} "
                    f"value={point.value:.4g} time={point.timestamp.isoformat()}"
                )
else:
    _ = UTC  # keep import used for type checkers when button not pressed
    st.info("Set filters and load the chart.")
