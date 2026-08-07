"""Visually distinct treatments for specification vs control limits (FR-C06).

Control limits are solid process boundaries. Specification limits are dashed
customer boundaries. The two never share line style, so conflation is a
deliberate visual edit rather than an accident of a shared token.
"""

from __future__ import annotations

CONTROL_LIMIT_STYLE = {
    "line": {"color": "#1f4e79", "width": 2, "dash": "solid"},
    "annotation_prefix": "CL",
    "legend_label": "Control limit",
}

SPEC_LIMIT_STYLE = {
    "line": {"color": "#8b4513", "width": 2, "dash": "dash"},
    "annotation_prefix": "SPEC",
    "legend_label": "Specification limit",
}

CENTRE_LINE_STYLE = {
    "line": {"color": "#1f4e79", "width": 1.5, "dash": "dot"},
    "legend_label": "Centre line",
}

VIOLATION_MARKER = {
    "symbol": "x",
    "size": 11,
    "color": "#b00020",
    "line_width": 2,
    "label": "OOC",
}
"""Shape and label — never colour alone (NFR-U03)."""
