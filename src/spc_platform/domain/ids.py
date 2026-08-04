"""Branded identifiers.

A lot ID and a wafer ID must not be silently swappable
(CODING_STANDARDS.md §3). ``NewType`` makes that a type error.
"""

from __future__ import annotations

from typing import NewType
from uuid import UUID

LotId = NewType("LotId", str)
WaferId = NewType("WaferId", str)
SiteId = NewType("SiteId", int)
ParameterId = NewType("ParameterId", str)
StepId = NewType("StepId", str)
ToolId = NewType("ToolId", str)
ChamberId = NewType("ChamberId", str)
RecipeId = NewType("RecipeId", str)
ProductId = NewType("ProductId", str)
MetrologyToolId = NewType("MetrologyToolId", str)
BaselineId = NewType("BaselineId", str)
MeasurementId = NewType("MeasurementId", UUID)
UnitSymbol = NewType("UnitSymbol", str)
DataRevision = NewType("DataRevision", str)
CodeRevision = NewType("CodeRevision", str)
ConfigRevision = NewType("ConfigRevision", str)
RuleId = NewType("RuleId", str)
ActorId = NewType("ActorId", str)
OcapId = NewType("OcapId", str)
