from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from heart_transplant.artifact_store import read_json, write_json
from heart_transplant.canonical_graph import build_canonical_graph, write_canonical_graph_for_artifact
from heart_transplant.classify.pipeline import run_classification_on_artifact
from heart_transplant.cli import app
from heart_transplant.evidence import (
    answer_with_evidence,
    explain_file,
    explain_node,
    query_codes,
    query_entities,
    query_projects,
    trace_dependency,
    trace_entity_workflow,
)
from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.models import StructuralArtifact, StructuralEdge
from heart_transplant.paper_checklist import build_paper_reproduction_checklist


def test_canonical_graph_unifies_structural_and_semantic_layers(tmp_path: Path) -> None:
    artifact_dir, artifact = _artifact_with_semantics(tmp_path)

    graph = build_canonical_graph(artifact_dir)

    assert graph["schema"] == "heart-transplant.canonical-graph.v1"
    assert graph["summary"]["dangling_edge_count"] == 0
    layers = set(graph["summary"]["layers"])
    assert {"system", "project", "file", "code", "semantic"} <= layers
    assert any(edge["provenance"]["producer"] == "semantic_classifier" for edge in graph["edges"])
    assert any(edge["edge_type"] == "RELATES_TO" for edge in graph["edges"])
    assert any(edge["source_id"] == "system:local" and edge["edge_type"] == "CONTAINS" for edge in graph["edges"])
    assert any(node["kind"] == "project_summary" for node in graph["nodes"])
    assert any(node["kind"] == "system_summary" for node in graph["nodes"])
    assert any(node["node_id"] == artifact.code_nodes[0].scip_id for node in graph["nodes"])
    assert graph["manifest"]["source_artifacts"]["structural"].endswith("structural-artifact.json")


def test_canonical_graph_can_project_temporal_multimodal_and_regret_reports(tmp_path: Path) -> None:
    artifact_dir, _artifact = _artifact_with_semantics(tmp_path)
    temporal = tmp_path / "temporal.json"
    temporal.write_text(
        json.dumps(
            {
                "replayed_snapshots": [
                    {
                        "commit_sha": "abc123",
                        "subject": "add auth",
                        "node_count": 2,
                        "edge_count": 1,
                        "file_node_count": 1,
                        "parser_backends": ["typescript"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    multimodal = tmp_path / "multimodal.json"
    multimodal.write_text(
        json.dumps(
            {
                "nodes": [{"node_id": "test:auth", "kind": "test", "path": "auth.test.ts", "name": "auth test"}],
                "edges": [{"source_id": "test:auth", "target_id": "codefile:auth.ts", "edge_kind": "TESTS"}],
            }
        ),
        encoding="utf-8",
    )
    regret = tmp_path / "regret.json"
    regret.write_text(
        json.dumps(
            {
                "surfaces": [
                    {
                        "regret": {"regret_id": "r1", "title": "Logging inconsistency"},
                        "evidence_bundle": [{"node_ids": ["codefile:auth.ts"], "summary": "auth.ts evidence"}],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    out = write_canonical_graph_for_artifact(
        artifact_dir,
        temporal_report=temporal,
        multimodal_report=multimodal,
        regret_report=regret,
    )
    graph = json.loads(out.read_text(encoding="utf-8"))
    layers = set(graph["summary"]["layers"])

    assert {"temporal", "test", "regret"} <= layers
    assert graph["manifest"]["source_artifacts"]["temporal"] == str(temporal.resolve())
    assert any(edge["edge_type"] == "EVIDENCED_BY" for edge in graph["edges"])
    assert all(edge["provenance"]["producer"] for edge in graph["edges"])
    assert all(node["provenance"]["producer"] for node in graph["nodes"])


def test_evidence_bundle_queries_return_receipts(tmp_path: Path) -> None:
    artifact_dir, artifact = _artifact_with_semantics(tmp_path)
    code_node = next(node for node in artifact.code_nodes if node.kind.value == "function")

    explained = explain_node(artifact_dir, code_node.scip_id)
    file_explained = explain_file(artifact_dir, "auth.ts")
    block = answer_with_evidence(artifact_dir, "Where is auth handled?")
    unsupported = answer_with_evidence(artifact_dir, "Where is Kafka configured?")
    missing_path = trace_dependency(artifact_dir, code_node.scip_id, "missing", max_depth=2)

    assert explained.source_nodes[0].node_id == code_node.scip_id
    assert explained.file_ranges
    assert file_explained.source_nodes
    assert block.query_type == "answer_with_evidence"
    assert block.source_nodes
    assert unsupported.query_type == "unsupported"
    assert not unsupported.source_nodes
    assert missing_path.confidence < 0.5
    assert missing_path.limitations


def test_entity_and_project_tools_return_paper_shaped_subgraphs(tmp_path: Path) -> None:
    artifact_dir, artifact = _artifact_with_semantics(tmp_path)

    entities = query_entities(artifact_dir, "auth session")
    workflow = trace_entity_workflow(artifact_dir, "auth session flow")
    projects = query_projects(artifact_dir, "auth project")
    codes = query_codes(artifact_dir, "sessionGuard", min_score=0.1)

    fn_node_id = next(node.scip_id for node in artifact.code_nodes if node.file_path == "auth.ts" and node.kind.value == "function")

    assert entities.query_type == "query_entities"
    assert entities.source_nodes
    assert entities.paths
    assert entities.paths[0].edge_provenance == [None]
    assert workflow.query_type == "trace_entity_workflow"
    assert workflow.paths
    assert projects.query_type == "query_projects"
    assert projects.paths[0].edge_types == ["CONTAINS"]
    assert codes.query_type == "query_codes"
    assert codes.source_nodes
    top_ids = [n.node_id for n in codes.source_nodes]
    assert fn_node_id in top_ids
    assert codes.paths
    assert max(len(p.node_ids) for p in codes.paths) >= 3
    assert any(len(p.edge_types) >= 2 for p in codes.paths)
    assert any(
        len(p.edge_types) >= 2 and any(x is not None for x in p.edge_provenance)
        for p in codes.paths
    )
    assert codes.source_excerpts


def test_query_codes_abstains_on_gibberish(tmp_path: Path) -> None:
    artifact_dir, _artifact = _artifact_with_semantics(tmp_path)
    empty = query_codes(artifact_dir, "zzzNonexistentSymbolXyzzy999")
    assert empty.query_type == "query_codes"
    assert empty.confidence == 0.0
    assert not empty.source_nodes


def test_answer_with_evidence_entity_vs_code_precedence(tmp_path: Path) -> None:
    """Entity-pattern questions route to trace_entity_workflow before query_codes."""
    artifact_dir, _artifact = _artifact_with_semantics(tmp_path)
    routed = answer_with_evidence(artifact_dir, "Which function creates the user entity?")
    assert routed.query_type == "trace_entity_workflow"


def test_answer_with_evidence_routes_code_questions_to_codes_tool(tmp_path: Path) -> None:
    artifact_dir, artifact = _artifact_with_semantics(tmp_path)
    fn_node_id = next(node.scip_id for node in artifact.code_nodes if node.file_path == "auth.ts" and node.kind.value == "function")
    routed = answer_with_evidence(artifact_dir, "Which function implements sessionGuard?")
    assert routed.query_type == "query_codes"
    assert routed.source_nodes
    assert fn_node_id in {n.node_id for n in routed.source_nodes}


def test_answer_with_evidence_hybrid_project_and_codes(tmp_path: Path) -> None:
    artifact_dir, _artifact = _artifact_with_semantics(tmp_path)
    hybrid = answer_with_evidence(artifact_dir, "What functions does the test/logiclens project expose?")
    assert hybrid.query_type == "query_projects_with_codes"
    assert hybrid.source_nodes
    assert hybrid.paths


def test_trace_dependency_respects_edge_direction(tmp_path: Path) -> None:
    artifact_dir, artifact = _artifact_with_semantics(tmp_path)
    auth_fn = next(n.scip_id for n in artifact.code_nodes if n.file_path == "auth.ts")
    db_fn = next(n.scip_id for n in artifact.code_nodes if n.file_path == "db.ts")
    fwd = trace_dependency(artifact_dir, auth_fn, db_fn, max_depth=4)
    assert fwd.query_type == "trace_dependency"
    assert fwd.confidence > 0.5
    rev = trace_dependency(artifact_dir, db_fn, auth_fn, max_depth=4)
    assert rev.confidence < 0.5


def test_answer_with_evidence_codes_abstention_benchmark_case(tmp_path: Path) -> None:
    artifact_dir, _artifact = _artifact_with_semantics(tmp_path)
    abstain = answer_with_evidence(artifact_dir, "Where is the function zzzNonexistentSymbolXyzzy999 implemented?")
    assert abstain.query_type == "query_codes"
    assert abstain.confidence == 0.0
    assert not abstain.source_nodes


def test_evidence_question_fixture_corpus_meets_phase17_minimum(tmp_path: Path) -> None:
    """Phase 17 retrieval gate expects a minimum corpus size before naming aggregate gates meaningful."""
    questions = Path(__file__).resolve().parents[2] / "docs" / "evals" / "evidence_questions.json"
    data = json.loads(questions.read_text(encoding="utf-8"))
    rows = [row for row in data if isinstance(row, dict) and row.get("status") == "active" and row.get("repo_name") == "test/logiclens"]
    assert len(rows) >= 20
    checklist = build_paper_reproduction_checklist(Path(__file__).resolve().parents[2])

    by_id = {feature.feature_id: feature for feature in checklist.features}
    assert checklist.feature_count >= 8
    assert by_id["structural_graph"].gate_or_test
    assert by_id["semantic_blocks"].benchmark_mapping
    assert by_id["evidence_retrieval"].status == "implemented"


def test_cli_exposes_logiclens_paper_path_commands(tmp_path: Path) -> None:
    artifact_dir, artifact = _artifact_with_semantics(tmp_path)
    code_node = next(node for node in artifact.code_nodes if node.kind.value == "function")
    runner = CliRunner()

    canonical = runner.invoke(app, ["canonical-graph", str(artifact_dir)])
    explain = runner.invoke(app, ["explain-node", code_node.scip_id, "--artifact-dir", str(artifact_dir)])
    entities = runner.invoke(app, ["query-entities", "auth session", "--artifact-dir", str(artifact_dir)])
    codes = runner.invoke(app, ["query-codes", "sessionGuard", "--artifact-dir", str(artifact_dir)])
    paper = runner.invoke(app, ["paper-checklist"])

    assert canonical.exit_code == 0
    assert json.loads(canonical.output)["schema"] == "heart-transplant.canonical-graph.v1"
    assert explain.exit_code == 0
    assert json.loads(explain.output)["query_type"] == "explain_node"
    assert entities.exit_code == 0
    assert json.loads(entities.output)["query_type"] == "query_entities"
    assert codes.exit_code == 0
    assert json.loads(codes.output)["query_type"] == "query_codes"
    assert paper.exit_code == 0
    assert json.loads(paper.output)["report_type"] == "logiclens_paper_reproduction_checklist"


def _artifact_with_semantics(tmp_path: Path) -> tuple[Path, object]:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function sessionGuard() { return true; }\n", encoding="utf-8")
    (repo / "db.ts").write_text(
        "export function persistSession() {\n  sessionGuard();\n  return 1;\n}\n",
        encoding="utf-8",
    )
    artifact = ingest_repository(repo, "test/logiclens")
    data = artifact.model_dump(mode="json")
    fn_id = next(str(n["scip_id"]) for n in data["code_nodes"] if n["file_path"] == "auth.ts")
    db_fn_id = next(str(n["scip_id"]) for n in data["code_nodes"] if n["file_path"] == "db.ts")
    file_auth = next(str(n["node_id"]) for n in data["file_nodes"] if n["file_path"] == "auth.ts")
    file_db = next(str(n["node_id"]) for n in data["file_nodes"] if n["file_path"] == "db.ts")
    proj_id = data["project_node"]["node_id"]
    edges_raw = list(data.get("edges") or [])
    edges_raw.extend(
        [
            StructuralEdge(
                source_id=file_auth,
                target_id=file_db,
                edge_type="DEPENDS_ON_FILE",
                repo_name="test/logiclens",
                provenance="fixture_cross_file",
            ).model_dump(mode="json"),
            StructuralEdge(
                source_id=fn_id,
                target_id=db_fn_id,
                edge_type="CALLS",
                repo_name="test/logiclens",
                provenance="scip",
            ).model_dump(mode="json"),
            StructuralEdge(
                source_id=proj_id,
                target_id=file_db,
                edge_type="CONTAINS",
                repo_name="test/logiclens",
                provenance="treesitter",
            ).model_dump(mode="json"),
        ]
    )
    data["edges"] = edges_raw
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    write_json(artifact_dir / "structural-artifact.json", data)
    run_classification_on_artifact(artifact_dir, use_openai=False)
    artifact_reload = StructuralArtifact.model_validate(read_json(artifact_dir / "structural-artifact.json"))
    return artifact_dir, artifact_reload
