"""Pipelines: the path from a raw export to a chartable series.

Discrete, independently testable stages, each recording lineage — input
revision, row counts in and out, transformations applied. Schema validation is
a hard stop, never a warning (SYSTEM_ARCHITECTURE.md §3.4).
"""
