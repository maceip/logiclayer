from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from heart_transplant.blast_radius import compute_impact_subgraph
from heart_transplant.db import graph_queries as gq
from heart_transplant.evidence import DEFAULT_CODES_MIN_SCORE, query_codes, query_entities, query_projects, trace_entity_workflow

mcp = FastMCP(
    "heart-transplant",
    instructions=(
        "Read-only graph tools backed by SurrealDB (ht_code, ht_edge, ht_block_assign). "
        "Set HEART_TRANSPLANT_SURREAL_URL (e.g. ws://127.0.0.1:8000) to point at a loaded graph."
    ),
)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


@mcp.tool()
def get_node(node_id: str) -> str:
    """Load one structural code node (``ht_code``) by id (`scip_id` / `node_id`)."""
    row = gq.get_code_node(node_id.strip())
    return _json(row if row else {"error": "not_found", "node_id": node_id})


@mcp.tool(name="get_neighbors")
def get_neighbors_mcp(
    node_id: str,
    direction: str = "both",
    limit: int = 200,
) -> str:
    """
    List incident edges in ``ht_edge`` for a node. ``direction`` is out | in | both.
    """
    d = direction if direction in ("out", "in", "both") else "both"
    r = gq.get_neighbors(node_id.strip(), direction=d, limit=limit)  # type: ignore[arg-type]
    return _json(r)


@mcp.tool(name="trace_symbol_path")
def trace_symbol_path_tool(
    start_id: str,
    end_id: str | None = None,
    max_depth: int = 8,
) -> str:
    """
    BFS over symbol-ish graph edges (REFERENCES, CALLS, CROSS_REFERENCE, …).
    If ``end_id`` is set, returns a path when one exists within ``max_depth`` hops.
    """
    s = start_id.strip()
    e = end_id.strip() if end_id else None
    r = gq.trace_symbol_path(s, e, max_depth=max_depth)
    return _json(r)


@mcp.tool(name="find_block_nodes")
def find_block_nodes_tool(
    block_label: str,
    min_confidence: float = 0.0,
    limit: int = 200,
) -> str:
    """List code nodes whose semantic block assignment (``ht_block_assign``) matches the label."""
    r = gq.find_block_nodes(block_label.strip(), min_confidence=min_confidence, with_code=True, limit=limit)
    return _json(r)


@mcp.tool()
def get_impact_radius(
    start_id: str,
    max_depth: int = 4,
    max_nodes: int = 200,
    high_degree_threshold: int = 80,
    prune_high_degree: bool = True,
) -> str:
    """
    Bounded impact subgraph: BFS from ``start_id`` over all edge types, with optional
    pruning of high-fanout nodes (keeps the start node).
    """
    r = compute_impact_subgraph(
        start_id.strip(),
        max_depth=max_depth,
        max_nodes=max_nodes,
        high_degree_threshold=high_degree_threshold,
        prune_high_degree=prune_high_degree,
    )
    return _json(r)


@mcp.tool(name="query_entities_artifact")
def query_entities_artifact_tool(
    artifact_dir: str,
    query: str,
    limit: int = 20,
) -> str:
    """Entity-centered retrieval from on-disk artifacts, matching the LogicLens Entities Tool shape."""

    return query_entities(Path(artifact_dir).expanduser().resolve(), query, limit=limit).model_dump_json(indent=2)


@mcp.tool(name="query_projects_artifact")
def query_projects_artifact_tool(
    artifact_dir: str,
    query: str,
    limit: int = 20,
) -> str:
    """Project-centered retrieval from on-disk artifacts, matching the LogicLens Projects Tool shape."""

    return query_projects(Path(artifact_dir).expanduser().resolve(), query, limit=limit).model_dump_json(indent=2)


@mcp.tool(name="query_codes_artifact")
def query_codes_artifact_tool(
    artifact_dir: str,
    query: str,
    limit: int = 20,
    subgraph_depth: int = 3,
    subgraph_max_edges: int = 120,
    min_score: float = DEFAULT_CODES_MIN_SCORE,
) -> str:
    """Code-centered retrieval from on-disk artifacts, matching the LogicLens Codes Tool shape."""

    return query_codes(
        Path(artifact_dir).expanduser().resolve(),
        query,
        limit=limit,
        subgraph_depth=subgraph_depth,
        subgraph_max_edges=subgraph_max_edges,
        min_score=min_score,
    ).model_dump_json(indent=2)


@mcp.tool(name="trace_entity_workflow_artifact")
def trace_entity_workflow_artifact_tool(
    artifact_dir: str,
    query: str,
    limit: int = 30,
) -> str:
    """Trace semantic code-to-entity action edges from on-disk artifacts."""

    return trace_entity_workflow(Path(artifact_dir).expanduser().resolve(), query, limit=limit).model_dump_json(indent=2)


def main() -> None:
    """Default stdio transport for IDE / Continue / Desktop MCP clients."""
    t = os.environ.get("HEART_TRANSPLANT_MCP_TRANSPORT", "stdio")
    if t not in ("stdio", "sse", "streamable-http"):
        t = "stdio"
    mcp.run(transport=t)  # type: ignore[arg-type]


if __name__ == "__main__":
    main()
