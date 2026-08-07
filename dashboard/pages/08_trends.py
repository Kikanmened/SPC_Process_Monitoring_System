"""Trends placeholder — Module 5 KPI requirements are proposed, not approved."""

from __future__ import annotations

import streamlit as st
from dashboard.components.refusal_panel import refusal_markdown
from dashboard.layouts.page import page_header

page_header(
    "Trends",
    "Descriptive navigation only until Module 5 KPI requirements are approved (Q5).",
)

st.markdown(
    refusal_markdown(
        "Trends unavailable",
        "FR-K01 - FR-K06 remain proposed and are not implementable. "
        "This screen will not invent KPI series. Use Control chart and Capability "
        "for approved time-window statistics.",
    )
)
