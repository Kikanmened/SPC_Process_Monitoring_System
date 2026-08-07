"""Render use-case refusals with equal prominence to successes (NFR-U05)."""

from __future__ import annotations


def refusal_markdown(title: str, reason: str) -> str:
    """Markdown block stating that a result was refused and why."""
    return (
        f"### {title}\n\n"
        f"**Refused.** {reason}\n\n"
        "No substitute value is shown. Resolve the underlying condition "
        "(for example, bring the process into control) and retry."
    )
