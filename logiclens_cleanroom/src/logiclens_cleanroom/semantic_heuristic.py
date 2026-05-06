from __future__ import annotations

import re

from logiclens_cleanroom.models import EdgeKind, EntityNode, GraphEdge, GraphNode, KnowledgeGraph, NodeKind, SemanticAction, SemanticLayer


def enrich_graph_heuristic(kg: KnowledgeGraph) -> KnowledgeGraph:
    """Deterministic semantic layer when no LLM is available (tests / offline)."""
    summaries: dict[str, str] = {}
    for n in kg.nodes.values():
        if n.kind != NodeKind.CODE:
            continue
        blob = f"{n.name} in {n.file_path} ({n.language})."
        content = (n.content or "")[:500]
        summaries[n.node_id] = f"{blob} Excerpt: {content}"

    project = next((x for x in kg.nodes.values() if x.kind == NodeKind.PROJECT), None)
    proj_name = project.name if project else "repo"
    block_counts: dict[str, int] = {}
    for text in summaries.values():
        for label, pat in [
            ("HTTP", r"\b(route|fetch|request|response|handler)\b"),
            ("Persistence", r"\b(db|database|sql|prisma|query)\b"),
            ("Auth", r"\b(auth|session|jwt|token|permission)\b"),
        ]:
            if re.search(pat, text, re.I):
                block_counts[label] = block_counts.get(label, 0) + 1
    top = ", ".join(sorted(block_counts, key=lambda k: -block_counts[k])[:5]) or "general application code"

    kg.semantic = SemanticLayer(
        code_summaries=summaries,
        project_summary=f"Project {proj_name} contains code touching: {top}.",
        system_summary=f"System view: single project {proj_name} in this graph snapshot.",
    )

    # Simple entity extraction from identifiers
    entity_names: dict[str, str] = {}
    for n in kg.nodes.values():
        if n.kind != NodeKind.CODE:
            continue
        for m in re.finditer(r"\b([A-Z][a-zA-Z0-9]{2,})\b", n.content or ""):
            name = m.group(1)
            if name in {"String", "Number", "Boolean", "Promise", "Error", "Date"}:
                continue
            entity_names.setdefault(name, n.node_id)

    from hashlib import sha256

    def eid(nm: str) -> str:
        return f"entity:{sha256(nm.encode()).hexdigest()[:12]}"

    entities: dict[str, EntityNode] = {}
    for name in list(entity_names.keys())[:25]:
        e = eid(name)
        entities[e] = EntityNode(entity_id=e, name=name, description=f"Inferred domain concept from code references to {name}.")

    project_id = next((x.node_id for x in kg.nodes.values() if x.kind == NodeKind.PROJECT), None)
    actions: list[SemanticAction] = []
    for name, src in list(entity_names.items())[:40]:
        e = eid(name)
        if e not in entities:
            continue
        actions.append(SemanticAction(source_code_id=src, entity_id=e, action="REFERENCES", reasoning="Heuristic reference from code token."))

    kg.entities = entities
    kg.actions = actions

    action_map = {"REFERENCES": EdgeKind.PRODUCE, "CREATE": EdgeKind.CREATE, "CONFIGURE": EdgeKind.CONFIGURE, "REPRESENTS": EdgeKind.REPRESENTS}
    for act in actions:
        ek = action_map.get(act.action, EdgeKind.PRODUCE)
        uid = sha256(f"{act.source_code_id}|{act.entity_id}|{act.action}".encode()).hexdigest()[:16]
        kg.edges.append(
            GraphEdge(edge_id=f"e_{uid}", source_id=act.source_code_id, target_id=act.entity_id, edge_type=ek, label=act.action)
        )

    if project_id:
        for eid_key in entities:
            uid = sha256(f"rel|{eid_key}|{project_id}".encode()).hexdigest()[:16]
            kg.edges.append(GraphEdge(edge_id=f"e_{uid}", source_id=eid_key, target_id=project_id, edge_type=EdgeKind.RELATES_TO))
            ent = kg.entities[eid_key]
            kg.nodes[eid_key] = GraphNode(
                node_id=eid_key,
                kind=NodeKind.ENTITY,
                name=ent.name,
                repo_name=proj_name,
                summary=ent.description,
            )

    for nid, text in summaries.items():
        if nid in kg.nodes:
            node = kg.nodes[nid]
            kg.nodes[nid] = GraphNode(**{**node.model_dump(), "summary": text})

    return kg
