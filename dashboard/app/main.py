"""Streamlit entry point - wires LocalBundle and navigates Module 9 screens."""

from __future__ import annotations

from pathlib import Path

import streamlit as st
from dashboard.state.demo_data import seed_demo_bundle
from dashboard.state.session import ensure_bundle

PAGES_DIR = Path(__file__).resolve().parents[1] / "pages"


def main() -> None:
    """Bootstrap session and run multipage navigation."""
    st.set_page_config(
        page_title="SPC Platform",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    bundle = ensure_bundle(st.session_state)  # type: ignore[arg-type]
    seed_demo_bundle(bundle)
    st.sidebar.markdown("### SPC Platform")
    st.sidebar.caption(f"config={bundle.services.config_revision} · actor via session (no SSO)")
    navigation = st.navigation(
        {
            "Monitor": [
                st.Page(
                    PAGES_DIR / "01_line_overview.py",
                    title="Line overview",
                    default=True,
                ),
                st.Page(PAGES_DIR / "02_control_chart.py", title="Control chart"),
                st.Page(PAGES_DIR / "07_alarm_queue.py", title="Alarm queue"),
            ],
            "Analyse": [
                st.Page(PAGES_DIR / "03_capability.py", title="Capability"),
                st.Page(PAGES_DIR / "04_msa.py", title="MSA / Gauge R&R"),
                st.Page(PAGES_DIR / "05_wafer_map.py", title="Wafer map"),
                st.Page(PAGES_DIR / "06_tool_comparison.py", title="Tool comparison"),
                st.Page(PAGES_DIR / "08_trends.py", title="Trends"),
            ],
        }
    )
    navigation.run()


if __name__ == "__main__":
    main()
