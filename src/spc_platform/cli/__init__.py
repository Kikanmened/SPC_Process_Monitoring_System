"""CLI: the Typer front door, and the entry point the scheduler drives.

One of three interchangeable driving adapters. Parses input, invokes one use
case, renders the result (SYSTEM_ARCHITECTURE.md §2, rule 5).
"""

from spc_platform.cli.app import app, create_cli, run

__all__ = ["app", "create_cli", "run"]
