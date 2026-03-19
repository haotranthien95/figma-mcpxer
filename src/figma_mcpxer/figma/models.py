from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FigmaNode(BaseModel):
    """Represents a Figma design node. Extra fields are preserved for full fidelity."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str
    name: str
    type: str
    visible: bool = True
    locked: bool = False
    children: list[FigmaNode] | None = None

    # Geometry — present on most rendered nodes
    absolute_bounding_box: dict[str, float] | None = Field(
        default=None, alias="absoluteBoundingBox"
    )
    absolute_render_bounds: dict[str, float] | None = Field(
        default=None, alias="absoluteRenderBounds"
    )

    # Text nodes
    characters: str | None = None

    # Component / Instance nodes
    component_id: str | None = Field(default=None, alias="componentId")
    description: str | None = None

    def child_count(self) -> int:
        return len(self.children) if self.children else 0


# Pydantic v2 requires this for self-referential models
FigmaNode.model_rebuild()


class ComponentMetadata(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    key: str
    name: str
    description: str = ""


class StyleMetadata(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    key: str
    name: str
    description: str = ""
    style_type: str = Field(alias="styleType")


class FigmaFile(BaseModel):
    """Response shape from GET /files/{file_key}."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    document: FigmaNode
    components: dict[str, Any] = Field(default_factory=dict)
    component_sets: dict[str, Any] = Field(default_factory=dict, alias="componentSets")
    styles: dict[str, Any] = Field(default_factory=dict)
    name: str
    last_modified: str = Field(alias="lastModified")
    version: str
    schema_version: int = Field(default=0, alias="schemaVersion")


class FigmaFileNodes(BaseModel):
    """Response shape from GET /files/{file_key}/nodes."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str
    version: str
    # Each value contains {document: Node, components: {...}, styles: {...}}
    nodes: dict[str, dict[str, Any]]
