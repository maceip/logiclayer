from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import typer
from openai import OpenAI

from logiclens_cleanroom.semantic_heuristic import enrich_graph_heuristic
from logiclens_cleanroom.semantic_llm import enrich_graph_with_llm
from logiclens_cleanroom.structural_ingest import build_structural_graph
from logiclens_cleanroom.tools import embed_graph_nodes

app = typer.Typer(no_args_is_help=True, help="LogicLens clean-room (arXiv:2601.10773) CLI.")


@app.command("build-graph")
def build_graph(
    repo: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    out: Path = typer.Option(..., "--out", help="Write knowledge-graph JSON here."),
    repo_name: str | None = typer.Option(None, "--repo-name"),
    use_openai: bool = typer.Option(False, "--use-openai", help="Run LLM semantic + embedding phases (needs OPENAI_API_KEY)."),
    chat_model: str = typer.Option("gpt-4o-mini", "--chat-model"),
) -> None:
    """Ingest repo into structural + semantic knowledge graph."""
    kg = build_structural_graph(repo.resolve(), repo_name=repo_name)
    if use_openai and os.environ.get("OPENAI_API_KEY"):
        client = OpenAI()
        kg = enrich_graph_with_llm(kg, client=client, chat_model=chat_model)
        embed_graph_nodes(kg, client)
    else:
        kg = enrich_graph_heuristic(kg)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(kg.to_json_dict(), indent=2), encoding="utf-8")
    typer.echo(json.dumps({"written": str(out.resolve()), "nodes": len(kg.nodes), "edges": len(kg.edges)}, indent=2))


@app.command("ask")
def ask(
    question: str = typer.Argument(...),
    graph: Path = typer.Option(..., "--graph", exists=True, dir_okay=False),
    use_openai: bool = typer.Option(False, "--use-openai"),
) -> None:
    """Run ReAct agent over a saved graph JSON."""
    from logiclens_cleanroom.models import KnowledgeGraph
    from logiclens_cleanroom.react_agent import run_react

    data = json.loads(graph.read_text(encoding="utf-8"))
    kg = KnowledgeGraph.model_validate(data)
    client = OpenAI() if use_openai and os.environ.get("OPENAI_API_KEY") else None
    if client:
        embed_graph_nodes(kg, client)
    result = run_react(kg, question, client=client)
    typer.echo(json.dumps(result, indent=2))
