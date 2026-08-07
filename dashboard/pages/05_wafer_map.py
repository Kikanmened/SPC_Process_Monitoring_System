"""Wafer map — Plotly primary; same WaferMapView drives static export."""

from __future__ import annotations

import streamlit as st
from dashboard.components.refusal_panel import refusal_markdown
from dashboard.components.wafer_map_figure import wafer_map_figure
from dashboard.components.wafer_map_static import render_wafer_map_png_bytes
from dashboard.layouts.page import page_header
from dashboard.state.session import default_actor, ensure_bundle

from spc_platform.application.use_cases import get_wafer_map
from spc_platform.common.errors import SPCPlatformError
from spc_platform.domain.ids import LotId, ParameterId, WaferId

page_header(
    "Wafer map",
    "True site coordinates (mm). Colour limits are fixed and shown numerically.",
)

bundle = ensure_bundle(st.session_state)  # type: ignore[arg-type]
parameter_id = st.text_input("Parameter", value="OXIDE_THK")
lot_id = st.text_input("Lot", value="LOT-DEMO")
wafer_id = st.text_input("Wafer", value="LOT-DEMO:1")
classify = st.checkbox("Classify spatial signature", value=False)
autoscale = st.checkbox(
    "Per-wafer colour autoscale (explicit, labelled)",
    value=False,
)
cmin = st.number_input("Fixed colour vmin (ignored if autoscale)", value=9.5)
cmax = st.number_input("Fixed colour vmax (ignored if autoscale)", value=10.5)

if st.button("Load wafer map", type="primary"):
    try:
        view = get_wafer_map(
            bundle.services,
            actor=default_actor(),
            parameter_id=ParameterId(parameter_id),
            lot_id=LotId(lot_id),
            wafer_id=WaferId(wafer_id),
            classify_spatial=classify,
            colour_vmin=None if autoscale else float(cmin),
            colour_vmax=None if autoscale else float(cmax),
            autoscale=autoscale,
        )
    except SPCPlatformError as exc:
        st.markdown(refusal_markdown("Wafer map unavailable", str(exc)))
    else:
        if view.is_aggregated and view.aggregation_message:
            st.warning(view.aggregation_message)
        st.plotly_chart(wafer_map_figure(view), use_container_width=True)
        st.caption(
            f"Colour scale {view.colour_scale.kind.value} "
            f"[{view.colour_scale.vmin:.4g}, {view.colour_scale.vmax:.4g}] "
            f"mode={view.colour_scale.mode.value} · "
            f"data_revision={view.data_revision} · n={view.n_sites_total}"
        )
        if view.spatial_signature is not None:
            st.write(
                f"Spatial signature: **{view.spatial_signature.value}** "
                f"(statistic={view.spatial_statistic})"
            )
        png = render_wafer_map_png_bytes(view)
        st.download_button(
            "Download static PNG (same WaferMapView)",
            data=png,
            file_name=f"{view.wafer_id}_map.png",
            mime="image/png",
        )
