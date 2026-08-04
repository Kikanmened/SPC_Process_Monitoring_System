"""Application layer: use cases and the ports they define.

Depends on ``domain``, ``analytics``, and port interfaces declared here; never
on a concrete adapter (SYSTEM_ARCHITECTURE.md §2, rule 3). Policy lives here —
the analytics layer computes what it is asked, and this layer decides what may
be asked.
"""
