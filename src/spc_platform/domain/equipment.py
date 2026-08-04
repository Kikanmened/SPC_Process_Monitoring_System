"""Equipment and route model: step, tool, chamber, recipe.

A chamber belongs to exactly one tool (SYSTEM_ARCHITECTURE.md §3.1). Equipment
is a tool → chamber hierarchy per SEMI E120/E125 conceptual alignment.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from spc_platform.domain.ids import ChamberId, RecipeId, StepId, ToolId


class ProcessStep(BaseModel):
    """A single named operation in the route."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    step_id: StepId
    name: str
    layer: str | None = None


class Tool(BaseModel):
    """A physical processing or metrology machine."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tool_id: ToolId
    step_id: StepId
    name: str
    is_metrology: bool = False


class Chamber(BaseModel):
    """An independently operating process volume within a tool."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    chamber_id: ChamberId
    tool_id: ToolId
    name: str


class Recipe(BaseModel):
    """The parameterised program executed by a tool for a step and product."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recipe_id: RecipeId
    step_id: StepId
    product_id: str
    name: str
    version: int = Field(ge=1)
