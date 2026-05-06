from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from logiclens_cleanroom.models import KnowledgeGraph
from logiclens_cleanroom.tools import (
    TOOL_SPECS,
    tool_codes,
    tool_entities,
    tool_graph_query,
    tool_projects,
    tool_source,
)


def _execute_tool(kg: KnowledgeGraph, name: str, args: dict[str, Any], client: OpenAI | None) -> dict[str, Any]:
    if name == "projects":
        return tool_projects(kg, str(args.get("query", "")), client=client)
    if name == "entities":
        return tool_entities(kg, str(args.get("query", "")), client=client)
    if name == "codes":
        return tool_codes(kg, str(args.get("query", "")), client=client)
    if name == "graph_query":
        return tool_graph_query(
            kg,
            str(args.get("op", "count_edges")),
            start_id=args.get("start_id"),
            end_id=args.get("end_id"),
            edge_type=args.get("edge_type"),
            max_depth=int(args.get("max_depth", 4)),
        )
    if name == "source":
        ids = args.get("node_ids")
        if isinstance(ids, str):
            ids = [ids]
        return tool_source(kg, list(ids or []))
    return {"error": "unknown_tool", "name": name}


def _openai_tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": "projects",
                "description": TOOL_SPECS[0]["description"],
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "entities",
                "description": TOOL_SPECS[1]["description"],
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "codes",
                "description": TOOL_SPECS[2]["description"],
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "graph_query",
                "description": TOOL_SPECS[3]["description"],
                "parameters": {
                    "type": "object",
                    "properties": {
                        "op": {"type": "string", "enum": ["neighborhood", "path", "count_edges", "list_entities"]},
                        "start_id": {"type": "string"},
                        "end_id": {"type": "string"},
                        "edge_type": {"type": "string"},
                        "max_depth": {"type": "integer"},
                    },
                    "required": ["op"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "source",
                "description": TOOL_SPECS[4]["description"],
                "parameters": {
                    "type": "object",
                    "properties": {"node_ids": {"type": "array", "items": {"type": "string"}}},
                    "required": ["node_ids"],
                },
            },
        },
    ]


def run_react(
    kg: KnowledgeGraph,
    question: str,
    *,
    client: OpenAI | None = None,
    model: str = "gpt-4o-mini",
    max_steps: int = 8,
) -> dict[str, Any]:
    """
    ReAct-style loop (paper §3.2): model selects among the five graph tools, observes JSON, answers.
    Without client, uses a deterministic multi-tool retrieval pass (offline tests).
    """
    trace: list[dict[str, Any]] = []

    if client is None:
        q = question.lower()
        packs: list[dict[str, Any]] = []
        if any(w in q for w in ("entity", "entities", "domain", "workflow", "flow", "business")):
            packs.append(tool_entities(kg, question, client=None))
        if any(w in q for w in ("project", "repo", "repository", "service", "microservice")):
            packs.append(tool_projects(kg, question, client=None))
        packs.append(tool_codes(kg, question, client=None))
        packs.append(tool_graph_query(kg, "count_edges"))
        trace.extend(packs)
        ranked = packs[0].get("ranked") if packs else None
        top_code = None
        if isinstance(ranked, list) and ranked:
            top_code = ranked[0].get("node_id")
        sources = tool_source(kg, [top_code]) if top_code else {"tool": "source", "sources": []}
        trace.append(sources)
        return {
            "mode": "offline_heuristic",
            "question": question,
            "tool_trace": trace,
            "summary": "Offline retrieval: combined entity/project/code subgraphs and optional top source.",
        }

    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": (
                "You are LogicLens (paper arXiv:2601.10773). You explore a software knowledge graph by calling tools. "
                "Use projects/entities/codes for retrieval, graph_query for structure, source for code text. "
                "After enough evidence, respond with a concise technical answer citing node_ids from tool output."
            ),
        },
        {"role": "user", "content": question},
    ]
    tools = _openai_tool_schemas()

    for _ in range(max_steps):
        resp = client.chat.completions.create(model=model, messages=messages, tools=tools, tool_choice="auto", temperature=0.1)
        msg = resp.choices[0].message
        if msg.tool_calls:
            messages.append(msg.model_dump())
            for call in msg.tool_calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = _execute_tool(kg, name, args, client)
                trace.append({"tool": name, "args": args, "result_keys": list(result.keys())})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, default=str)[:24000],
                    }
                )
            continue
        text = msg.content or ""
        return {"mode": "openai_react", "question": question, "answer": text, "tool_trace": trace}

    return {"mode": "openai_react", "question": question, "error": "max_steps_exceeded", "tool_trace": trace}
