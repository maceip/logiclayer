from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from openai import OpenAI

from logiclens_cleanroom.embeddings import cosine_similarity, embed_texts_sync
from logiclens_cleanroom.models import EdgeKind, KnowledgeGraph, NodeKind
from logiclens_cleanroom.structural_ingest import induced_subgraph


def _text_for_code(n: Any) -> str:
    parts = [n.name or "", n.file_path or "", n.summary or "", (n.content or "")[:6000]]
    return "\n".join(p for p in parts if p)


def _text_for_entity(name: str, desc: str) -> str:
    return f"{name}\n{desc}"


def embed_graph_nodes(kg: KnowledgeGraph, client: OpenAI, model: str = "text-embedding-3-small") -> None:
    """Populate node.embedding for semantic retrieval (paper-style vector indexing)."""
    texts: list[str] = []
    ids: list[str] = []
    project = next((n for n in kg.nodes.values() if n.kind == NodeKind.PROJECT), None)
    proj_blob = ""
    if project:
        proj_blob = f"{project.name}\n{kg.semantic.project_summary or ''}\n{kg.semantic.system_summary or ''}"
        ids.append(project.node_id)
        texts.append(proj_blob)

    for n in kg.nodes.values():
        if n.kind == NodeKind.CODE:
            ids.append(n.node_id)
            texts.append(_text_for_code(n))
        elif n.kind == NodeKind.ENTITY:
            ids.append(n.node_id)
            texts.append(_text_for_entity(n.name, n.summary or ""))

    if not texts:
        return
    vectors = embed_texts_sync(client, model, texts)
    for nid, vec in zip(ids, vectors, strict=True):
        node = kg.nodes.get(nid)
        if node:
            kg.nodes[nid] = type(node)(**{**node.model_dump(), "embedding": vec})


def tool_projects(kg: KnowledgeGraph, query: str, client: OpenAI | None = None, top_k: int = 3) -> dict[str, Any]:
    """Paper Projects Tool: semantic selection + expand to adjacent code."""
    project = next((n for n in kg.nodes.values() if n.kind == NodeKind.PROJECT), None)
    if not project:
        return {"tool": "projects", "nodes": [], "subgraph": {}}

    if client and project.embedding:
        qv = embed_texts_sync(client, "text-embedding-3-small", [query])[0]
        score = cosine_similarity(qv, project.embedding)
    else:
        qlow = query.lower()
        blob = f"{project.name} {kg.semantic.project_summary or ''}".lower()
        score = 1.0 if any(t in blob for t in qlow.split() if len(t) > 2) else 0.3

    seed = {project.node_id}
    sub = induced_subgraph(kg, seed, depth=2)
    return {"tool": "projects", "relevance": score, "subgraph": sub.to_json_dict()}


def tool_entities(kg: KnowledgeGraph, query: str, client: OpenAI | None = None, top_k: int = 5) -> dict[str, Any]:
    """Paper Entities Tool: vector match on entities, include incoming action edges."""
    entities = [(nid, n) for nid, n in kg.nodes.items() if n.kind == NodeKind.ENTITY]
    if not entities:
        return {"tool": "entities", "matches": [], "subgraph": {}}

    scored: list[tuple[float, str]] = []
    if client:
        qv = embed_texts_sync(client, "text-embedding-3-small", [query])[0]
        for nid, n in entities:
            if n.embedding:
                scored.append((cosine_similarity(qv, n.embedding), nid))
            else:
                scored.append((0.0, nid))
    else:
        qterms = [t for t in query.lower().split() if len(t) > 2]
        for nid, n in entities:
            blob = f"{n.name} {n.summary or ''}".lower()
            hit = sum(1 for t in qterms if t in blob)
            scored.append((float(hit), nid))

    scored.sort(key=lambda x: -x[0])
    seed = {nid for _s, nid in scored[:top_k] if _s > 0 or not client}
    if not seed and entities:
        seed = {entities[0][0]}
    sub = induced_subgraph(kg, seed, depth=2)
    return {"tool": "entities", "ranked": [{"node_id": nid, "score": s} for s, nid in scored[:top_k]], "subgraph": sub.to_json_dict()}


def tool_codes(kg: KnowledgeGraph, query: str, client: OpenAI | None = None, top_k: int = 8) -> dict[str, Any]:
    """Paper Codes Tool: semantic search over code units."""
    codes = [n for n in kg.nodes.values() if n.kind == NodeKind.CODE]
    scored: list[tuple[float, str]] = []
    if client:
        qv = embed_texts_sync(client, "text-embedding-3-small", [query])[0]
        for n in codes:
            if n.embedding:
                scored.append((cosine_similarity(qv, n.embedding), n.node_id))
            else:
                scored.append((0.0, n.node_id))
    else:
        qlow = query.lower()
        for n in codes:
            blob = _text_for_code(n).lower()
            hit = sum(1 for t in qlow.split() if len(t) > 2 and t in blob)
            scored.append((float(hit), n.node_id))
    scored.sort(key=lambda x: -x[0])
    seed = {nid for s, nid in scored[:top_k] if s > 0}
    if not seed and codes:
        seed = {scored[0][1]}
    sub = induced_subgraph(kg, seed, depth=1)
    return {"tool": "codes", "ranked": [{"node_id": nid, "score": s} for s, nid in scored[:top_k]], "subgraph": sub.to_json_dict()}


def tool_source(kg: KnowledgeGraph, node_ids: list[str]) -> dict[str, Any]:
    """Paper Source Tool: return implementations."""
    out = []
    for nid in node_ids:
        n = kg.nodes.get(nid)
        if n and n.kind == NodeKind.CODE:
            out.append(
                {
                    "node_id": n.node_id,
                    "file_path": n.file_path,
                    "range": n.range.model_dump() if n.range else None,
                    "content": n.content,
                    "summary": n.summary,
                }
            )
    return {"tool": "source", "sources": out}


def tool_graph_query(
    kg: KnowledgeGraph,
    op: str,
    *,
    start_id: str | None = None,
    end_id: str | None = None,
    edge_type: str | None = None,
    max_depth: int = 4,
) -> dict[str, Any]:
    """
    Paper Graph Query Tool: bounded analytical queries over the in-memory graph.
    ops: neighborhood | path | count_edges | list_entities
    """
    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for e in kg.edges:
        adj[e.source_id].append((e.target_id, e.edge_type.value))
        adj[e.target_id].append((e.source_id, e.edge_type.value))

    if op == "list_entities":
        ents = [n.model_dump() for n in kg.nodes.values() if n.kind == NodeKind.ENTITY]
        return {"tool": "graph_query", "op": op, "entities": ents}

    if op == "count_edges":
        return {"tool": "graph_query", "op": op, "edge_count": len(kg.edges), "node_count": len(kg.nodes)}

    if op == "neighborhood" and start_id:
        q = deque([(start_id, 0)])
        seen = {start_id}
        nodes = {start_id}
        edges_used: list[dict[str, str]] = []
        while q:
            nid, d = q.popleft()
            if d >= max_depth:
                continue
            for nb, et in adj.get(nid, []):
                if edge_type and et != edge_type:
                    continue
                edges_used.append({"from": nid, "to": nb, "type": et})
                if nb not in seen:
                    seen.add(nb)
                    nodes.add(nb)
                    q.append((nb, d + 1))
        return {
            "tool": "graph_query",
            "op": op,
            "nodes": list(nodes),
            "edges": edges_used[:500],
        }

    if op == "path" and start_id and end_id:
        q = deque([(start_id, [start_id])])
        seen = {start_id}
        while q:
            nid, path = q.popleft()
            if nid == end_id:
                return {"tool": "graph_query", "op": op, "path": path}
            if len(path) > max_depth:
                continue
            for nb, et in adj.get(nid, []):
                if edge_type and et != edge_type:
                    continue
                if nb not in seen:
                    seen.add(nb)
                    q.append((nb, path + [nb]))
        return {"tool": "graph_query", "op": op, "path": None}

    return {"tool": "graph_query", "error": f"unknown op {op} or missing ids"}


TOOL_SPECS = [
    {"name": "projects", "description": "Retrieve subgraph focused on project(s) for structure/workflow questions."},
    {"name": "entities", "description": "Retrieve subgraph around domain entities for cross-cutting functional questions."},
    {"name": "codes", "description": "Retrieve subgraph around code units for implementation questions."},
    {"name": "graph_query", "description": "Run analytical graph query: neighborhood, path, count_edges, list_entities."},
    {"name": "source", "description": "Fetch full source for code node ids."},
]
