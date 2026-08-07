"""Dashboard must not import analytics (Module 9 hard constraint)."""

from __future__ import annotations

import ast
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parents[3] / "dashboard"


def test_dashboard_sources_do_not_import_analytics() -> None:
    offenders: list[str] = []
    for path in DASHBOARD.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("spc_platform.analytics"):
                        offenders.append(f"{path}:{alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("spc_platform.analytics"):
                    offenders.append(f"{path}:{module}")
    assert offenders == []
