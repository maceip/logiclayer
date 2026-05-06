from __future__ import annotations

from pathlib import Path

from logiclens_cleanroom.react_agent import run_react
from logiclens_cleanroom.semantic_heuristic import enrich_graph_heuristic
from logiclens_cleanroom.structural_ingest import build_multi_repo_graph, build_structural_graph
from logiclens_cleanroom.tools import tool_codes, tool_graph_query, tool_source


def test_structural_graph_has_paper_schema_layers(tmp_path: Path) -> None:
    repo = tmp_path / "svc"
    repo.mkdir()
    (repo / "api.ts").write_text(
        'import { db } from "./db";\nexport function handleOrder() { return db.save(); }\n',
        encoding="utf-8",
    )
    (repo / "db.ts").write_text("export const db = { save() {} };\n", encoding="utf-8")

    kg = build_structural_graph(repo, repo_name="orders-api")
    kinds = {n.kind.value for n in kg.nodes.values()}
    assert "system" in kinds
    assert "project" in kinds
    assert "file" in kinds
    assert "code" in kinds
    et = {e.edge_type.value for e in kg.edges}
    assert "CONTAINS" in et
    assert "DEPENDS_ON" in et


def test_multi_repo_merges_under_one_system(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "x.ts").write_text("export const x = 1;\n", encoding="utf-8")
    (b / "y.ts").write_text("export const y = 2;\n", encoding="utf-8")

    kg = build_multi_repo_graph([(a, "repo-a"), (b, "repo-b")])
    projects = [n for n in kg.nodes.values() if n.kind.value == "project"]
    assert len(projects) == 2
    sys_edges = [e for e in kg.edges if e.source_id == kg.system_id]
    assert len(sys_edges) >= 2


def test_heuristic_semantic_adds_entities_and_actions(tmp_path: Path) -> None:
    repo = tmp_path / "r"
    repo.mkdir()
    (repo / "m.ts").write_text("class OrderProcessor { process(o: Order) {} }\n", encoding="utf-8")

    kg = enrich_graph_heuristic(build_structural_graph(repo, "orders"))
    assert kg.semantic.code_summaries
    assert kg.entities
    assert any(n.kind.value == "entity" for n in kg.nodes.values())


def test_five_tools_smoke(tmp_path: Path) -> None:
    repo = tmp_path / "r2"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function login() { return true; }\n", encoding="utf-8")
    kg = enrich_graph_heuristic(build_structural_graph(repo, "app"))

    assert tool_graph_query(kg, "count_edges")["edge_count"] > 0
    c = tool_codes(kg, "login", client=None)
    assert c["tool"] == "codes"
    ranked = c.get("ranked") or []
    assert ranked
    nid = ranked[0]["node_id"]
    src = tool_source(kg, [nid])
    assert src["sources"] and src["sources"][0]["content"]


def test_react_offline_returns_trace(tmp_path: Path) -> None:
    repo = tmp_path / "r3"
    repo.mkdir()
    (repo / "x.ts").write_text("export function foo() {}\n", encoding="utf-8")
    kg = enrich_graph_heuristic(build_structural_graph(repo, "x"))
    out = run_react(kg, "Where is foo implemented?", client=None)
    assert out["mode"] == "offline_heuristic"
    assert out["tool_trace"]
