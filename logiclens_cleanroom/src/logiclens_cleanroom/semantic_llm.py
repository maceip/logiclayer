from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from openai import OpenAI

from logiclens_cleanroom.models import EdgeKind, EntityNode, GraphEdge, GraphNode, KnowledgeGraph, NodeKind, SemanticAction, SemanticLayer


def _chat_json(client: OpenAI, model: str, system: str, user: str) -> dict[str, Any]:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    raw = resp.choices[0].message.content or "{}"
    return json.loads(raw)


def enrich_graph_with_llm(
    kg: KnowledgeGraph,
    *,
    client: OpenAI | None = None,
    chat_model: str = "gpt-4o-mini",
    max_code_nodes_per_batch: int = 40,
) -> KnowledgeGraph:
    """
    Paper semantic phases: per-code summaries, project/system synthesis, entities + actions.
    Requires OPENAI_API_KEY when client is None.
    """
    c = client or OpenAI()
    code_nodes = [n for n in kg.nodes.values() if n.kind == NodeKind.CODE]
    summaries: dict[str, str] = {}

    for i in range(0, len(code_nodes), max_code_nodes_per_batch):
        batch = code_nodes[i : i + max_code_nodes_per_batch]
        payload = [
            {
                "node_id": n.node_id,
                "fqn": n.fqn,
                "file": n.file_path,
                "excerpt": (n.content or "")[:4000],
            }
            for n in batch
        ]
        data = _chat_json(
            c,
            chat_model,
            system="You produce concise technical summaries for a software knowledge graph. Output JSON: {\"items\": [{\"node_id\": string, \"summary\": string}]} — exactly three sentences per item.",
            user=json.dumps({"code_units": payload}),
        )
        for item in data.get("items", []):
            nid = str(item.get("node_id", ""))
            summ = str(item.get("summary", "")).strip()
            if nid and summ:
                summaries[nid] = summ

    project = next((n for n in kg.nodes.values() if n.kind == NodeKind.PROJECT), None)
    proj_name = project.name if project else "project"

    proj_data = _chat_json(
        c,
        chat_model,
        system="Summarize repository role for a multi-repo system graph. JSON: {\"project_summary\": string} — 4-6 sentences.",
        user=json.dumps({"project": proj_name, "code_summaries": list(summaries.values())[:80]}),
    )
    project_summary = str(proj_data.get("project_summary", ""))

    sys_data = _chat_json(
        c,
        chat_model,
        system="Synthesize a system-level overview. JSON: {\"system_summary\": string} — 3-5 sentences.",
        user=json.dumps({"project_summaries": [project_summary]}),
    )
    system_summary = str(sys_data.get("system_summary", ""))

    entity_payload = _chat_json(
        c,
        chat_model,
        system=(
            "Extract domain entities and how code operates on them (LogicLens semantic graph). "
            "JSON schema: {\"entities\": [{\"name\": string, \"description\": string}], "
            "\"actions\": [{\"source_code_id\": string, \"entity_name\": string, \"action\": string, \"reasoning\": string}]} "
            "Use actions CREATE, PRODUCE, CONFIGURE, REPRESENTS as appropriate."
        ),
        user=json.dumps(
            {
                "summaries": [{"node_id": k, "text": v} for k, v in list(summaries.items())[:60]],
            }
        ),
    )

    def _eid(name: str) -> str:
        return f"entity:{sha256(name.encode()).hexdigest()[:12]}"

    entities: dict[str, EntityNode] = {}
    for ent in entity_payload.get("entities", []):
        ename = str(ent.get("name", "")).strip()
        if not ename:
            continue
        eid = _eid(ename)
        entities[eid] = EntityNode(entity_id=eid, name=ename, description=str(ent.get("description", "")))

    name_to_id = {e.name: eid for eid, e in entities.items()}
    actions: list[SemanticAction] = []
    for act in entity_payload.get("actions", []):
        sid = str(act.get("source_code_id", ""))
        en = str(act.get("entity_name", "")).strip()
        eid = name_to_id.get(en)
        if not sid or not eid:
            continue
        actions.append(
            SemanticAction(
                source_code_id=sid,
                entity_id=eid,
                action=str(act.get("action", "RELATES")).upper(),
                reasoning=str(act.get("reasoning", "")),
            )
        )

    kg.semantic = SemanticLayer(
        code_summaries=summaries,
        project_summary=project_summary or None,
        system_summary=system_summary or None,
    )
    kg.entities = entities
    kg.actions = actions

    project_id = next((n.node_id for n in kg.nodes.values() if n.kind == NodeKind.PROJECT), None)
    action_map = {
        "CREATE": EdgeKind.CREATE,
        "PRODUCE": EdgeKind.PRODUCE,
        "CONFIGURE": EdgeKind.CONFIGURE,
        "REPRESENTS": EdgeKind.REPRESENTS,
    }
    for act in actions:
        ek = action_map.get(act.action.upper(), EdgeKind.PRODUCE)
        uid = sha256(f"{act.source_code_id}|{act.entity_id}|{act.action}".encode()).hexdigest()[:16]
        kg.edges.append(
            GraphEdge(
                edge_id=f"e_{uid}",
                source_id=act.source_code_id,
                target_id=act.entity_id,
                edge_type=ek,
                label=act.action,
            )
        )
    if project_id:
        for eid in entities:
            uid = sha256(f"rel|{eid}|{project_id}".encode()).hexdigest()[:16]
            kg.edges.append(
                GraphEdge(
                    edge_id=f"e_{uid}",
                    source_id=eid,
                    target_id=project_id,
                    edge_type=EdgeKind.RELATES_TO,
                )
            )
            ent = kg.entities[eid]
            kg.nodes[eid] = GraphNode(
                node_id=eid,
                kind=NodeKind.ENTITY,
                name=ent.name,
                repo_name=project.name if project else "",
                summary=ent.description,
            )

    # Attach summaries to nodes for tooling
    for nid, text in summaries.items():
        if nid in kg.nodes:
            n = kg.nodes[nid]
            kg.nodes[nid] = GraphNode(**{**n.model_dump(), "summary": text})

    return kg
