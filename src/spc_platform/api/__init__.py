"""API: the FastAPI front door.

One of three interchangeable driving adapters. Parses input, invokes one use
case, renders the result (SYSTEM_ARCHITECTURE.md §2, rule 5).
"""

from spc_platform.api.app import create_app

__all__ = ["create_app"]
