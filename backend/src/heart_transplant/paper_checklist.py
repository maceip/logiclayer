from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


class PaperFeatureStatus(BaseModel):
    feature_id: str
    paper_feature: str
    backend_mapping: str
    status: Literal["implemented", "partial", "missing"]
    gate_or_test: str
    artifact: str
    benchmark_mapping: str | None = None
    notes: list[str] = Field(default_factory=list)


class PaperReproductionChecklist(BaseModel):
    report_type: str = "logiclens_paper_reproduction_checklist"
    feature_count: int
    implemented: int
    partial: int
    missing: int
    features: list[PaperFeatureStatus]


def build_paper_reproduction_checklist(repo_root: Path | None = None) -> PaperReproductionChecklist:
    root = (repo_root or Path(__file__).resolve().parents[3]).resolve()
    features = [
        PaperFeatureStatus(
            feature_id="structural_graph",
            paper_feature="Repository program graph construction",
            backend_mapping="Tree-sitter ingest, FileNode/CodeNode graph, canonical graph export",
            status="implemented" if (root / "backend/src/heart_transplant/ingest/treesitter_ingest.py").is_file() else "missing",
            gate_or_test="backend/tests/test_ingest.py; validate-gates structural_ingest_produces_nodes",
            artifact="structural-artifact.json; canonical-graph.json",
            benchmark_mapping="Graph coverage contributes to block-benchmark missing-node rate.",
        ),
        PaperFeatureStatus(
            feature_id="symbol_identity",
            paper_feature="Stable symbol identity and reference graph",
            backend_mapping="SCIP index/consume, DEFINES/REFERENCES/CROSS_REFERENCE edges, orphan promotion",
            status="partial",
            gate_or_test="backend/tests/test_scip_consume.py; validate-gates scip_actually_resolves_nodes",
            artifact="index.scip; scip-index.json; scip-consumed.json; orphaned-symbols.json",
            benchmark_mapping="No direct paper benchmark committed; identity quality is measured by resolved_symbol_rate and orphaned_symbol_rate.",
            notes=["References exist, but cross-repo/reference completeness is not yet paper-grade."],
        ),
        PaperFeatureStatus(
            feature_id="semantic_blocks",
            paper_feature="Semantic component/block labeling",
            backend_mapping="24-block ontology, deterministic classifier, semantic artifact",
            status="partial",
            gate_or_test="block-benchmark; backend/tests/test_gold_benchmark.py",
            artifact="semantic-artifact.json; docs/evals/gold_block_benchmark*.json",
            benchmark_mapping="block-benchmark reports end-to-end accuracy, scorable accuracy, missing-node rate, per-block confusion.",
            notes=["Holdout baseline is below target; multi-label and file-surface scoring are now present."],
        ),
        PaperFeatureStatus(
            feature_id="semantic_entities",
            paper_feature="Semantic graph enhancement with domain entities and action edges",
            backend_mapping="SemanticEntity/SemanticAction generation, canonical Entity nodes, Code→Entity action edges, Entity→Project RELATES_TO edges",
            status="partial",
            gate_or_test="backend/tests/test_logiclens_paper_path.py::test_entity_and_project_tools_return_paper_shaped_subgraphs",
            artifact="semantic-artifact.json; canonical-graph.json",
            benchmark_mapping="Covered indirectly by evidence-benchmark today; a dedicated entity/workflow fixture set is still needed.",
            notes=["Entity/action extraction is deterministic and artifact-backed; LLM-grade domain abstraction remains future work."],
        ),
        PaperFeatureStatus(
            feature_id="evidence_retrieval",
            paper_feature="Evidence-grounded architecture question answering",
            backend_mapping="EvidenceBundle schema and artifact-backed explain/trace/find/answer helpers",
            status="implemented",
            gate_or_test="evidence-benchmark (Phase 17); docs/evals/evidence_benchmark_report.json; backend/tests/test_evidence_benchmark.py::test_evidence_benchmark_meets_phase17_thresholds",
            artifact="docs/evals/evidence_questions.json; docs/evals/fixtures/logiclens-evidence-benchmark/; docs/evals/evidence_benchmark_report.json",
            benchmark_mapping="Committed fixture: 28 active test/logiclens rows; accuracy >= 0.80 and hallucination_rate == 0 enforced in CI.",
            notes=[
                "Real-repo variance for evidence-benchmark is Phase 18; parity is declared only on the committed logiclens fixture corpus.",
            ],
        ),
        PaperFeatureStatus(
            feature_id="reactive_graph_tools",
            paper_feature="Agent retrieval tools for Projects, Entities, Codes, Graph Query, and Source",
            backend_mapping="Artifact-backed project/entity/code/workflow retrieval, explain-node/source as Source tool, Surreal graph queries, MCP tools",
            status="partial",
            gate_or_test="backend/tests/test_logiclens_paper_path.py; backend/tests/test_graph_queries.py",
            artifact="canonical-graph.json; semantic-artifact.json; SurrealDB ht_code/ht_edge/ht_block_assign rows",
            benchmark_mapping="Evidence benchmark covers answer quality; tool-selection quality is not yet evaluated with a ReAct harness.",
            notes=[
                "CLI/MCP expose query-projects, query-entities, query-codes, trace-entity-workflow; explain-node traces Source tool behavior.",
                "Graph Query remains Surreal-backed (gq.*); full arbitrary graph DB queries from artifacts are not paper-identical.",
            ],
        ),
        PaperFeatureStatus(
            feature_id="graph_persistence",
            paper_feature="Queryable graph backend",
            backend_mapping="SurrealDB load/verify and MCP graph query tools",
            status="partial",
            gate_or_test="backend/tests/test_surreal_phase3.py; validate-gates graph_smoke_structure_is_consistent",
            artifact="SurrealDB ht_code/ht_edge rows derived from structural-artifact.json",
            benchmark_mapping="Persistence is gate-based, not benchmark-scored.",
            notes=["Artifact-backed evidence helpers reduce dependence on a running DB for reproducibility."],
        ),
        PaperFeatureStatus(
            feature_id="temporal_reasoning",
            paper_feature="Architecture evolution over time",
            backend_mapping="temporal-scan, temporal snapshots/diffs, replayed Tree-sitter snapshots",
            status="partial",
            gate_or_test="backend/tests/test_temporal_scan.py; temporal-gates",
            artifact="phase-9 temporal reports; replayed_snapshots",
            benchmark_mapping="Temporal benchmark maps to replayed diff correctness and drift precision/recall fixtures.",
            notes=["SCIP + semantic replay is planned but not required on every commit yet."],
        ),
        PaperFeatureStatus(
            feature_id="multi_modal",
            paper_feature="Cross-layer reasoning over code, tests, API, and infra",
            backend_mapping="multimodal-ingest plus canonical graph cross-layer nodes/edges",
            status="partial",
            gate_or_test="backend/tests/test_phase_10_13.py; graph-integrity",
            artifact="multimodal ingest JSON; canonical-graph.json",
            benchmark_mapping="Future benchmark should score test/API/infra correlation accuracy.",
        ),
        PaperFeatureStatus(
            feature_id="regret_sdk",
            paper_feature="Actionable remediation planning on graph evidence",
            backend_mapping="RegretSurface, evidence bundle, surgery plan, execution ledger",
            status="partial",
            gate_or_test="backend/tests/test_phase_10_13.py; regret-sdk-scan",
            artifact="regret-sdk-scan JSON",
            benchmark_mapping="Future benchmark maps to regret fixture precision and plan specificity review.",
            notes=["This goes beyond the paper target and must stay evidence-gated."],
        ),
    ]
    counts = {status: sum(1 for item in features if item.status == status) for status in ("implemented", "partial", "missing")}
    return PaperReproductionChecklist(
        feature_count=len(features),
        implemented=counts["implemented"],
        partial=counts["partial"],
        missing=counts["missing"],
        features=features,
    )
