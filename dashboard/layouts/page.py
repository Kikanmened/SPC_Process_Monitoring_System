"""Common page chrome."""

from __future__ import annotations

import streamlit as st


def page_header(title: str, subtitle: str) -> None:
    """Render a single-purpose page title and supporting sentence."""
    st.title(title)
    st.caption(subtitle)
