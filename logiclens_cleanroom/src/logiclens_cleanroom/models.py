from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EdgeKind(str, Enum):
    CONTAINS = "CONTAINS"
    DEPENDS_ON = "DEPENDS_ON"
    CALLS = "CALLS"
    IMPLEMENTS = "IMPLEMENTS"
    CREATE = "CREATE"
    PRODUCE = "PRODUCE"
    CONFIGURE = "CONFIGURE"
    REPRESENTS = "REPRESENTS"
    RELATES_TO = "RELATES_TO"


class NodeKind(str, Enum):
    SYSTEM = "system"
    PROJECT = "project"
    FILE = "file"
    CODE = "code"
    ENTITY = "entity"


class SourceRange(BaseModel):
    start_line: int
    start_col: int
    end_line: int
    end_col: int


class GraphNode(BaseModel):
    node_id: str
    kind: NodeKind
    name: str
    repo_name: str
    language: str | None = None
    file_path: str | None = None
    fqn: str | None = None
    range: SourceRange | None = None
    content: str | None = None
    embedding: list[float] | None = None
    summary: str | None = None


class GraphEdge(BaseModel):
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeKind
    label: str | None = None


class SemanticLayer(BaseModel):
    """LLM-produced descriptions matching the paper's semantic graph phase."""

    code_summaries: dict[str, str] = Field(default_factory=dict)
    project_summary: str | None = None
    system_summary: str | None = None


class EntityNode(BaseModel):
    entity_id: str
    name: str
    description: str
    embedding: list[float] | None = None


class SemanticAction(BaseModel):
    source_code_id: str
    entity_id: str
    action: str
    reasoning: str


class KnowledgeGraph(BaseModel):
    """Full graph: structural + semantic summaries + entities (paper Section 3.1)."""

    system_id: str
    nodes: dict[str, GraphNode] = Field(default_factory=dict)
    edges: list[GraphEdge] = Field(default_factory=list)
    semantic: SemanticLayer = Field(default_factory=SemanticLayer)
    entities: dict[str, EntityNode] = Field(default_factory=dict)
    actions: list[SemanticAction] = Field(default_factory=list)

    def edge_index(self) -> dict[str, list[tuple[str, EdgeKind, str]]]:
        """adjacency: node_id -> [(neighbor_id, edge_type, direction out|in)]."""
        out: dict[str, list[tuple[str, EdgeKind, str]]] = {}
        for e in self.edges:
            out.setdefault(e.source_id, []).append((e.target_id, e.edge_type, "out"))
            out.setdefault(e.target_id, []).append((e.source_id, e.edge_type, "in"))
        return out

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
