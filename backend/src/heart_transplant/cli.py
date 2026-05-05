from __future__ import annotations

import json
from pathlib import Path

import typer

from heart_transplant.artifact_manifest import build_artifact_manifest, run_artifact_manifest, summarize_artifact_manifest, write_artifact_manifest
from heart_transplant.artifact_store import artifact_root, persist_structural_artifact, write_json
from heart_transplant.canonical_graph import build_canonical_graph
from heart_transplant.evidence import answer_with_evidence, DEFAULT_CODES_MIN_SCORE, explain_file, explain_node, find_architectural_block, query_codes, query_entities, query_projects, trace_dependency, trace_entity_workflow
from heart_transplant.graph_smoke import run_graph_smoke
from heart_transplant.ingest.corpus_ingest import ingest_vendors
from heart_transplant.ingest.treesitter_ingest import ingest_repository
from heart_transplant.ontology import iter_blocks
from heart_transplant.paper_checklist import build_paper_reproduction_checklist
from heart_transplant.phase_metrics import collect_phase_metrics
from heart_transplant.classify.pipeline import persist_semantic_to_surreal, run_classification_on_artifact
from heart_transplant.db.surreal_loader import load_artifact
from heart_transplant.db.verify import verify_artifact_in_db
from heart_transplant.evals.build_gold import write_gold_from_ground_truth
from heart_transplant.evals.corpus_gate import evaluate_corpus_gate
from heart_transplant.evals.evidence_benchmark import load_evidence_questions, run_evidence_benchmark
from heart_transplant.evals.gold_audit import audit_gold_file
from heart_transplant.evals.gold_benchmark import build_block_benchmark_report, load_gold_set
from heart_transplant.graph_integrity import run_graph_integrity
from heart_transplant.maximize.report import build_maximize_report, write_maximize_report
from heart_transplant.maximize.gates import run_maximize_gates
from heart_transplant.scip_consume import consume_scip_artifact
from heart_transplant.scip.symbol_index import build_symbol_index_from_artifacts, save_symbol_index
from heart_transplant.scip_typescript import run_scip_typescript_index
from heart_transplant.temporal.diff import architecture_diff
from heart_transplant.temporal.drift import detect_architectural_drift
from heart_transplant.temporal.gates import run_temporal_gates
from heart_transplant.temporal.metrics import temporal_metrics, write_temporal_metrics
from heart_transplant.temporal.persist import persist_temporal_metrics
from heart_transplant.temporal.scan import temporal_scan, write_temporal_scan
from heart_transplant.temporal.snapshot import architecture_snapshot
from heart_transplant.training import build_training_packet
from heart_transplant.causal.simulation import run_change_simulation
from heart_transplant.demo import run_logiclens_demo
from heart_transplant.regret.scan import run_regret_scan, run_regret_sdk_scan
from heart_transplant.execution.orchestrator import run_transplant
from heart_transplant.multimodal.ingest import run_multimodal_ingest
from heart_transplant.surface.status import program_surface_status
from heart_transplant.validation_gates import latest_artifact_dir, run_validation_gates

app = typer.Typer(no_args_is_help=True, help="Canonical backend CLI for heart-transplant.")


@app.command("list-blocks")
def list_blocks() -> None:
    for block in iter_blocks():
        typer.echo(block)


@app.command("beta-serve")
def beta_serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Host/interface to bind."),
    port: int = typer.Option(8089, "--port", help="Port to bind."),
    docs_dir: Path | None = typer.Option(None, "--docs-dir", exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Serve the beta console and unauthenticated hosted analysis API."""

    from heart_transplant.beta_api import serve_beta

    serve_beta(host=host, port=port, docs_dir=docs_dir.resolve() if docs_dir else None)


@app.command("ingest-local")
def ingest_local(
    repo_path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    repo_name: str | None = typer.Option(None, "--repo-name", help="Override the repo name stored in the artifact."),
    with_scip: bool = typer.Option(False, "--with-scip", help="Also generate a real SCIP index with scip-typescript."),
    install_deps: bool = typer.Option(False, "--install-deps", help="Install Node dependencies before running SCIP when needed."),
) -> None:
    """Parse a local repo into CodeNode records using Tree-sitter."""

    resolved_path = repo_path.resolve()
    inferred_name = repo_name or resolved_path.name
    artifact = ingest_repository(repo_path=resolved_path, repo_name=inferred_name)
    target_dir = persist_structural_artifact(artifact)
    scip_metadata = None

    if with_scip:
        scip_metadata = run_scip_typescript_index(
            resolved_path,
            inferred_name,
            target_dir,
            install_deps=install_deps,
        )
        write_json(target_dir / "scip-index.json", scip_metadata.model_dump(mode="json"))
        scip_consumed = consume_scip_artifact(
            target_dir,
            global_symbol_index_path=None,
        )
        write_json(target_dir / "scip-consumed.json", scip_consumed)
    else:
        scip_consumed = None

    manifest = write_artifact_manifest(target_dir, command="ingest-local")
    typer.echo(
        json.dumps(
            {
                "repo_name": artifact.repo_name,
                "repo_path": artifact.repo_path,
                "artifact_dir": str(target_dir),
                "node_count": artifact.node_count,
                "edge_count": artifact.edge_count,
                "parser_backends": artifact.parser_backends,
                "scip": scip_metadata.model_dump(mode="json") if scip_metadata else None,
                "scip_consumed": scip_consumed,
                "manifest": manifest,
            },
            indent=2,
        )
    )


@app.command("test-graph")
def test_graph(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit with code 1 if SCIP is present on disk but no nodes resolved (symbol_source=scip).",
    ),
) -> None:
    """Run a structural smoke test against a stored graph artifact."""

    report = run_graph_smoke(artifact_dir)
    typer.echo(json.dumps(report, indent=2))
    if strict and str(report.get("scip_integration_status", "")).startswith("fail:"):
        raise typer.Exit(code=1)


@app.command("run-manifest")
def run_manifest(
    target: Path = typer.Argument(..., exists=True, help="Artifact directory or artifact-manifest.json path."),
    write: bool = typer.Option(True, "--write/--no-write", help="Write artifact-manifest.json when target is an artifact directory."),
    execute_commands: bool = typer.Option(False, "--execute-commands", help="Run additional manifest commands when present."),
) -> None:
    """Generate or run the artifact manifest receipt for an existing ingest run."""

    resolved = target.resolve()
    if resolved.is_dir():
        report = write_artifact_manifest(resolved) if write else build_artifact_manifest(resolved)
        typer.echo(json.dumps(report, indent=2))
        if not report["summary"]["required_artifacts_present"]:
            raise typer.Exit(code=1)
        return

    report = run_artifact_manifest(resolved, execute_commands=execute_commands)
    typer.echo(json.dumps(report, indent=2))
    if report["summary"]["overall_status"] != "pass":
        raise typer.Exit(code=1)


@app.command("current-status")
def current_status(
    manifest: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """Summarize artifact manifest status without executing commands."""

    typer.echo(json.dumps(summarize_artifact_manifest(manifest.resolve()), indent=2))


@app.command("canonical-graph")
def canonical_graph(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    out: Path | None = typer.Option(None, "--out", help="Optional JSON output path."),
) -> None:
    """Export one canonical architecture graph across structural, semantic, and report layers."""

    report = build_canonical_graph(artifact_dir.resolve())
    if out:
        write_json(out.resolve(), report)
    typer.echo(json.dumps(report, indent=2))


@app.command("explain-node")
def explain_node_command(
    node_id: str,
    artifact_dir: Path = typer.Option(..., "--artifact-dir", exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Return a LogicLens evidence bundle explaining one node from artifact JSON."""

    typer.echo(explain_node(artifact_dir.resolve(), node_id).model_dump_json(indent=2))


@app.command("explain-file")
def explain_file_command(
    file_path: str,
    artifact_dir: Path = typer.Option(..., "--artifact-dir", exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Return evidence for all nodes materialized from a file path."""

    typer.echo(explain_file(artifact_dir.resolve(), file_path).model_dump_json(indent=2))


@app.command("trace-dependency")
def trace_dependency_command(
    start_id: str,
    end_id: str | None = typer.Option(None, "--end-id"),
    artifact_dir: Path = typer.Option(..., "--artifact-dir", exists=True, file_okay=False, dir_okay=True),
    max_depth: int = typer.Option(5, "--max-depth"),
) -> None:
    """Trace an artifact-local graph path and return evidence with node/edge receipts."""

    typer.echo(trace_dependency(artifact_dir.resolve(), start_id, end_id=end_id, max_depth=max_depth).model_dump_json(indent=2))


@app.command("find-architectural-block")
def find_architectural_block_command(
    block_label: str,
    artifact_dir: Path = typer.Option(..., "--artifact-dir", exists=True, file_okay=False, dir_okay=True),
    min_confidence: float = typer.Option(0.0, "--min-confidence"),
) -> None:
    """Find block-assigned nodes with evidence rather than prose-only answers."""

    resolved_artifact_dir = artifact_dir.resolve()
    bundle = find_architectural_block(resolved_artifact_dir, block_label)
    if min_confidence > 0:
        semantic_path = resolved_artifact_dir / "semantic-artifact.json"
        semantic_rows = json.loads(semantic_path.read_text(encoding="utf-8")).get("block_assignments", [])
        allowed_node_ids = {
            row.get("node_id")
            for row in semantic_rows
            if float(row.get("confidence") or 0.0) >= min_confidence
        }
        bundle.source_nodes = [node for node in bundle.source_nodes if node.node_id in allowed_node_ids]
    typer.echo(bundle.model_dump_json(indent=2))


@app.command("query-entities")
def query_entities_command(
    query: str,
    artifact_dir: Path = typer.Option(..., "--artifact-dir", exists=True, file_okay=False, dir_okay=True),
    limit: int = typer.Option(20, "--limit"),
) -> None:
    """Return an entity-centered subgraph evidence bundle from semantic artifacts."""

    typer.echo(query_entities(artifact_dir.resolve(), query, limit=limit).model_dump_json(indent=2))


@app.command("query-projects")
def query_projects_command(
    query: str,
    artifact_dir: Path = typer.Option(..., "--artifact-dir", exists=True, file_okay=False, dir_okay=True),
    limit: int = typer.Option(20, "--limit"),
) -> None:
    """Return a project-centered evidence bundle from summaries and adjacent code nodes."""

    typer.echo(query_projects(artifact_dir.resolve(), query, limit=limit).model_dump_json(indent=2))


@app.command("query-codes")
def query_codes_command(
    query: str,
    artifact_dir: Path = typer.Option(..., "--artifact-dir", exists=True, file_okay=False, dir_okay=True),
    limit: int = typer.Option(20, "--limit"),
    subgraph_depth: int = typer.Option(3, "--subgraph-depth"),
    subgraph_max_edges: int = typer.Option(120, "--subgraph-max-edges"),
    min_score: float = typer.Option(DEFAULT_CODES_MIN_SCORE, "--min-score", help="Abstain when best normalized lexical score is below this."),
) -> None:
    """Return a code-centered evidence bundle (LogicLens paper Codes Tool shape)."""

    typer.echo(
        query_codes(
            artifact_dir.resolve(),
            query,
            limit=limit,
            subgraph_depth=subgraph_depth,
            subgraph_max_edges=subgraph_max_edges,
            min_score=min_score,
        ).model_dump_json(indent=2)
    )


@app.command("trace-entity-workflow")
def trace_entity_workflow_command(
    query: str,
    artifact_dir: Path = typer.Option(..., "--artifact-dir", exists=True, file_okay=False, dir_okay=True),
    limit: int = typer.Option(30, "--limit"),
) -> None:
    """Trace code-to-entity action edges for workflow-style questions."""

    typer.echo(trace_entity_workflow(artifact_dir.resolve(), query, limit=limit).model_dump_json(indent=2))


@app.command("answer-with-evidence")
def answer_with_evidence_command(
    question: str,
    artifact_dir: Path = typer.Option(..., "--artifact-dir", exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Answer a narrow architecture question from artifact evidence, or say evidence is insufficient."""

    typer.echo(answer_with_evidence(artifact_dir.resolve(), question).model_dump_json(indent=2))


@app.command("fixture-candidates")
def fixture_candidates(
    target: Path = typer.Argument(..., exists=True, help="Repo directory or existing artifact directory."),
    repo_name: str | None = typer.Option(None, "--repo-name", help="Repo name for fresh ingest targets."),
    out_dir: Path | None = typer.Option(None, "--out-dir", help="Directory for review packet files."),
    with_scip: bool = typer.Option(False, "--with-scip", help="Run SCIP when target is a source repo."),
    install_deps: bool = typer.Option(False, "--install-deps", help="Install deps before SCIP when needed."),
    use_openai: bool = typer.Option(False, "--use-openai", help="Use OpenAI during classification if OPENAI_API_KEY is set."),
) -> None:
    """One-command reviewer packet: ingest/classify if needed, then emit candidates to approve/correct."""

    result = build_training_packet(
        target.resolve(),
        repo_name=repo_name,
        out_dir=out_dir.resolve() if out_dir else None,
        with_scip=with_scip,
        install_deps=install_deps,
        use_openai=use_openai,
    )
    typer.echo(json.dumps(result, indent=2))


@app.command("paper-checklist")
def paper_checklist(
    artifact_dir: Path | None = typer.Option(None, "--artifact-dir", exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Map LogicLens paper features to implementation status, gates/tests, artifacts, and benchmarks."""

    checklist = build_paper_reproduction_checklist(artifact_dir.resolve() if artifact_dir else None)
    typer.echo(checklist.model_dump_json(indent=2))


@app.command("consume-scip")
def consume_scip(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    strict: bool = typer.Option(
        False,
        "--strict",
        help="Exit with code 1 when index.scip exists but zero code nodes get SCIP identity.",
    ),
    symbol_index: Path | None = typer.Option(
        None,
        "--symbol-index",
        help="Optional merged corpus symbol index JSON for cross-repo reference resolution.",
    ),
) -> None:
    """Parse and consume a real SCIP index into the stored structural artifact."""

    report = consume_scip_artifact(artifact_dir, global_symbol_index_path=symbol_index.resolve() if symbol_index else None)
    typer.echo(json.dumps(report, indent=2))
    if strict and (artifact_dir / "index.scip").exists() and not int(
        report.get("resolution", {}).get("nodes_with_scip_identity", 0)  # type: ignore[union-attr]
        or 0
    ):
        raise typer.Exit(code=1)


@app.command("ingest-vendor-corpus")
def ingest_vendor_corpus(
    root: Path = typer.Argument(
        "vendor/github-repos",
        help="Directory containing one subdirectory per repository (e.g. vendor/github-repos).",
    ),
    report_path: Path | None = typer.Option(
        None,
        "--write-report",
        help="Write JSON summary to this path (default: .heart-transplant/artifacts/corpus-ingest.json).",
    ),
) -> None:
    """Run canonical Tree-sitter ingest on every subfolder; reports failures, never silent-skip errors."""

    resolved = root.resolve()
    if not resolved.is_dir():
        raise typer.BadParameter(f"Not a directory: {resolved}")
    out = report_path.resolve() if report_path else (artifact_root() / "corpus-ingest.json")
    summary = ingest_vendors(resolved, output_report=out)
    typer.echo(json.dumps(summary, indent=2))
    if summary["failed"]:
        raise typer.Exit(code=1)


@app.command("build-corpus-symbols")
def build_corpus_symbols(
    out: Path = typer.Option(
        None,
        "--out",
        help="Output path (default: .heart-transplant/artifacts/corpus-symbol-index.json).",
    ),
    roots: list[Path] = typer.Argument(
        default_factory=list,
        help="Each directory should contain a structural-artifact.json (e.g. multiple artifact folders).",
    ),
) -> None:
    """Merge ``code_nodes`` from several artifact dirs for multi-repo SCIP cross-reference."""

    if roots:
        paths = [p.resolve() for p in roots]
    else:
        paths = [p for p in artifact_root().iterdir() if p.is_dir() and (p / "structural-artifact.json").is_file()]
    if not paths:
        raise typer.Exit(code=1)
    idx = build_symbol_index_from_artifacts(paths)
    dest = (out or (artifact_root() / "corpus-symbol-index.json")).resolve()
    save_symbol_index(dest, idx)
    typer.echo(json.dumps({"wrote": str(dest), "symbol_count": idx.get("symbol_count", 0)}, indent=2))


@app.command("load-surreal")
def load_surreal(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Load structural (and ``semantic-artifact.json`` if present) into SurrealDB."""

    r = load_artifact(artifact_dir)
    typer.echo(json.dumps(r, indent=2))


@app.command("verify-surreal")
def verify_surreal(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Check Surreal record counts match the on-disk structural artifact for the same repo."""

    r = verify_artifact_in_db(artifact_dir)
    typer.echo(json.dumps(r, indent=2))
    if not r.get("pass"):
        raise typer.Exit(code=1)


@app.command("classify")
def classify_artifact(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    use_openai: bool = typer.Option(
        True,
        help="If false, use keyword heuristic only. If true and OPENAI_API_KEY is set, use the OpenAI API.",
    ),
) -> None:
    """Run neighborhood-aware block classification; writes ``semantic-artifact.json``."""

    sem = run_classification_on_artifact(artifact_dir, use_openai=use_openai)
    typer.echo(sem.model_dump_json(indent=2))


@app.command("persist-semantic-surreal")
def persist_semantic_surreal(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Load ``semantic-artifact.json`` block rows into Surreal (requires ``classify`` first)."""

    n = persist_semantic_to_surreal(artifact_dir)
    typer.echo(json.dumps({"rows_loaded": n}, indent=2))


@app.command("validate-gates")
def validate_gates(
    repo_path: Path | None = typer.Option(None, "--repo-path", exists=True, file_okay=False, dir_okay=True, help="Repo path to validate against. Defaults to the repo_path recorded in the artifact."),
    artifact_dir: Path | None = typer.Option(None, "--artifact-dir", exists=True, file_okay=False, dir_okay=True, help="Artifact directory to validate. Defaults to the latest artifact."),
) -> None:
    """Run simple truthfulness gates against real code and artifacts."""

    chosen_artifact_dir = artifact_dir.resolve() if artifact_dir else latest_artifact_dir()
    structural = json.loads((chosen_artifact_dir / "structural-artifact.json").read_text(encoding="utf-8"))
    chosen_repo_path = repo_path.resolve() if repo_path else Path(str(structural["repo_path"])).resolve()
    report = run_validation_gates(chosen_repo_path, chosen_artifact_dir)
    typer.echo(json.dumps(report, indent=2))


@app.command("mcp-serve")
def mcp_serve() -> None:
    """Start the stdio MCP server (graph tools); same as ``python -m heart_transplant.mcp_server``."""

    from heart_transplant.mcp_server import main as mcp_main

    mcp_main()


@app.command("phase-metrics")
def phase_metrics(
    artifact_dir: Path | None = typer.Option(None, "--artifact-dir", exists=True, file_okay=False, dir_okay=True, help="Artifact directory to inspect. Defaults to the latest artifact."),
    repo_path: Path | None = typer.Option(None, "--repo-path", exists=True, file_okay=False, dir_okay=True, help="Override repo path. Defaults to the repo_path recorded in the artifact."),
    gold_set: Path | None = typer.Option(None, "--gold-set", exists=True, dir_okay=False, help="Optional gold benchmark JSON for the evaluation phase."),
    classify_if_missing: bool = typer.Option(False, "--classify-if-missing", help="If semantic-artifact.json is missing, run the current classifier before reporting metrics."),
    use_openai: bool = typer.Option(False, "--use-openai", help="When classifying, use OpenAI if OPENAI_API_KEY is present."),
) -> None:
    """Emit raw per-phase metrics without embedding private pass/fail thresholds in the repo."""

    chosen_artifact_dir = artifact_dir.resolve() if artifact_dir else latest_artifact_dir()
    report = collect_phase_metrics(
        chosen_artifact_dir,
        repo_path=repo_path.resolve() if repo_path else None,
        gold_set_path=gold_set.resolve() if gold_set else None,
        classify_if_missing=classify_if_missing,
        use_openai=use_openai,
    )
    typer.echo(json.dumps(report, indent=2))


@app.command("build-gold")
def build_gold(
    ground_truth: Path = typer.Argument(..., exists=True, dir_okay=False, help="vendored-ground-truth.json path."),
    out: Path = typer.Option("docs/evals/gold_block_benchmark.json", "--out", help="Output benchmark JSON."),
    repo_name: str | None = typer.Option(None, "--repo-name", help="Optional repoName filter from the ground-truth file."),
    max_items: int = typer.Option(40, "--max-items", help="Maximum gold items to emit."),
    include_medium: bool = typer.Option(
        True,
        "--include-medium/--no-include-medium",
        help="Include medium-confidence ground-truth rows (recommended for Phase 8.5 breadth).",
    ),
    exclude_repo: list[str] = typer.Option(
        [],
        "--exclude-repo",
        help="Repeatable. repoName values to omit (e.g. holdout repo for the main benchmark file).",
    ),
    only_repo: str | None = typer.Option(
        None,
        "--only-repo",
        help="If set, only emit items for this repoName (e.g. holdout-only benchmark).",
    ),
) -> None:
    """Create artifact-stable file-level block benchmark items from vendored ground truth."""

    excl = frozenset(exclude_repo) if exclude_repo else None
    only = frozenset({only_repo}) if only_repo else None
    items = write_gold_from_ground_truth(
        ground_truth.resolve(),
        out.resolve(),
        repo_name=repo_name,
        max_items=max_items,
        include_medium=include_medium,
        exclude_repo_names=excl,
        only_repo_names=only,
    )
    typer.echo(json.dumps({"wrote": str(out.resolve()), "item_count": len(items)}, indent=2))


@app.command("gold-audit")
def gold_audit(
    gold_set: Path = typer.Argument(..., exists=True, dir_okay=False, help="Gold benchmark JSON to audit."),
) -> None:
    """Rail 1: audit gold rows before optimizing classifier or graph behavior."""

    report = audit_gold_file(gold_set.resolve())
    typer.echo(json.dumps(report, indent=2))
    if report.get("summary", {}).get("overall_status") != "pass":
        raise typer.Exit(code=1)


@app.command("block-benchmark")
def block_benchmark(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    gold_set: Path = typer.Option(
        ...,
        "--gold-set",
        exists=True,
        dir_okay=False,
        help="Gold benchmark JSON.",
    ),
    out: Path | None = typer.Option(None, "--out", help="Optional JSON report path."),
) -> None:
    """Track 2: report semantic block quality separately from graph materialization coverage."""

    chosen_artifact_dir = artifact_dir.resolve()
    structural = json.loads((chosen_artifact_dir / "structural-artifact.json").read_text(encoding="utf-8"))
    report = build_block_benchmark_report(
        structural,
        load_gold_set(gold_set.resolve()),
        artifact_dir=chosen_artifact_dir,
        gold_set_path=gold_set.resolve(),
    )
    if out:
        write_json(out.resolve(), report)
    typer.echo(json.dumps(report, indent=2))


@app.command("evidence-benchmark")
def evidence_benchmark(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    questions: Path = typer.Option(
        "docs/evals/evidence_questions.json",
        "--questions",
        exists=True,
        dir_okay=False,
        help="Evidence question JSON set.",
    ),
    out: Path | None = typer.Option(None, "--out", help="Optional JSON report path."),
    fail_on_hallucinations: bool = typer.Option(
        False,
        "--fail-on-hallucinations",
        help="Exit non-zero when unsupported rows hallucinate (evidence where abstention expected).",
    ),
) -> None:
    """Score evidence-backed architecture answers against expected files and blocks."""

    report = run_evidence_benchmark(
        artifact_dir.resolve(),
        load_evidence_questions(questions.resolve()),
        question_set_path=questions.resolve(),
        fail_on_hallucinations=fail_on_hallucinations,
    )
    if out:
        write_json(out.resolve(), report)
    typer.echo(json.dumps(report, indent=2))
    hr = float(report["summary"].get("hallucination_rate") or 0.0)
    if report["summary"]["accuracy"] < 0.8:
        raise typer.Exit(code=1)
    if fail_on_hallucinations and hr > 0.0:
        raise typer.Exit(code=1)


@app.command("corpus-gate")
def corpus_gate(
    results_jsonl: Path = typer.Argument(..., exists=True, dir_okay=False),
    min_attempted: int = typer.Option(50, "--min-attempted", help="Minimum repository attempts required."),
    min_ok_rate: float = typer.Option(1.0, "--min-ok-rate", help="Minimum successful ingest+metrics rate."),
    max_ingest_failed: int = typer.Option(0, "--max-ingest-failed", help="Maximum allowed ingest failures."),
    max_zero_node_ok: int = typer.Option(0, "--max-zero-node-ok", help="Maximum successful artifacts allowed to have zero code nodes."),
) -> None:
    """Evaluate a multi-repo corpus run as a trust and quality-gate artifact."""

    report = evaluate_corpus_gate(
        results_jsonl.resolve(),
        min_attempted=min_attempted,
        min_ok_rate=min_ok_rate,
        max_ingest_failed=max_ingest_failed,
        max_zero_node_ok=max_zero_node_ok,
    )
    typer.echo(json.dumps(report, indent=2))
    if report["summary"]["overall_status"] != "pass":
        raise typer.Exit(code=1)


@app.command("graph-integrity")
def graph_integrity(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Track 3: gate dangling graph targets and synthetic/provisional leakage."""

    report = run_graph_integrity(artifact_dir.resolve())
    typer.echo(json.dumps(report, indent=2))
    if report["summary"]["overall_status"] != "pass":
        raise typer.Exit(code=1)


@app.command("maximize-audit")
def maximize_audit(
    artifact_dir: Path | None = typer.Option(None, "--artifact-dir", exists=True, file_okay=False, dir_okay=True, help="Artifact directory to audit. Defaults to latest artifact."),
    gold_set: Path | None = typer.Option(None, "--gold-set", exists=True, dir_okay=False, help="Optional gold benchmark JSON."),
    out: Path | None = typer.Option(None, "--out", help="Output JSON path. Defaults to .heart-transplant/reports/<timestamp>__phase-8-5-audit.json."),
    no_validation: bool = typer.Option(False, "--no-validation", help="Skip fresh validation gates for a faster report."),
) -> None:
    """Write a Phase 8.5 current-capability audit report."""

    chosen_artifact_dir = artifact_dir.resolve() if artifact_dir else latest_artifact_dir()
    report = build_maximize_report(
        chosen_artifact_dir,
        gold_set_path=gold_set.resolve() if gold_set else None,
        include_validation=not no_validation,
    )
    dest = write_maximize_report(report, out.resolve() if out else None)
    typer.echo(json.dumps({"wrote": str(dest), "summary": report["summary"], "known_limitations": report["known_limitations"]}, indent=2))


@app.command("maximize-report")
def maximize_report_cmd(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    gold_set: Path | None = typer.Option(
        None,
        "--gold-set",
        exists=True,
        dir_okay=False,
        help="Optional gold benchmark JSON.",
    ),
    skip_validation: bool = typer.Option(False, "--skip-validation", help="Skip fresh validation gates."),
) -> None:
    """Print the full Phase 8.5 capability report as JSON (for tooling and maximize-gates demos)."""

    report = build_maximize_report(
        artifact_dir.resolve(),
        gold_set_path=gold_set.resolve() if gold_set else None,
        include_validation=not skip_validation,
    )
    typer.echo(json.dumps(report, indent=2))


@app.command("maximize-gates")
def maximize_gates_cmd(
    artifact_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    gold_set: Path = typer.Option(
        ...,
        "--gold-set",
        exists=True,
        dir_okay=False,
        help="Gold benchmark JSON (Phase 8.5 breadth thresholds).",
    ),
    holdout_artifact_dir: Path | None = typer.Option(
        None,
        "--holdout-artifact-dir",
        exists=True,
        file_okay=False,
        dir_okay=True,
    ),
    holdout_gold_set: Path | None = typer.Option(
        None,
        "--holdout-gold-set",
        exists=True,
        dir_okay=False,
        help="Optional holdout-only gold benchmark JSON. Defaults to --gold-set.",
    ),
    skip_demos: bool = typer.Option(False, "--skip-demos", help="Skip five-CLI JSON replay checks."),
) -> None:
    """Run Phase 8.5 maximize gates; exits 1 if any gate fails."""

    report = run_maximize_gates(
        artifact_dir.resolve(),
        gold_set.resolve(),
        holdout_artifact_dir=holdout_artifact_dir.resolve() if holdout_artifact_dir else None,
        holdout_gold_set_path=holdout_gold_set.resolve() if holdout_gold_set else None,
        run_demos=not skip_demos,
    )
    typer.echo(json.dumps(report, indent=2))
    if report["summary"]["overall_status"] != "pass":
        raise typer.Exit(code=1)


@app.command("temporal-scan")
def temporal_scan_command(
    repo_path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    max_commits: int = typer.Option(50, "--max-commits", help="Maximum commits to inspect."),
    since: str | None = typer.Option(None, "--since", help="Optional git --since value, e.g. 2026-01-01."),
    replay_snapshots: bool = typer.Option(False, "--replay-snapshots", help="Replay Tree-sitter ingest on selected historical commits."),
    replay_limit: int = typer.Option(5, "--replay-limit", help="Maximum commits to replay when --replay-snapshots is set."),
    out: Path | None = typer.Option(None, "--out", help="Output JSON path. Defaults to .heart-transplant/reports/<timestamp>__phase-9-temporal-scan.json."),
) -> None:
    """Phase 9 deterministic git-history scan with block-churn metrics."""

    report = temporal_scan(
        repo_path.resolve(),
        max_commits=max_commits,
        since=since,
        replay_snapshots=replay_snapshots,
        replay_limit=replay_limit,
    )
    dest = write_temporal_scan(report, out.resolve() if out else None)
    typer.echo(json.dumps({"wrote": str(dest), "commit_count": report.commit_count, "block_churn": report.block_churn}, indent=2))


@app.command("temporal-snapshot")
def temporal_snapshot_command(
    repo_path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    ref: str = typer.Option("HEAD", "--ref", help="Git ref/commit to snapshot."),
) -> None:
    """Phase 9: immutable file/block architecture snapshot for one commit."""

    snapshot = architecture_snapshot(repo_path.resolve(), ref)
    typer.echo(snapshot.model_dump_json(indent=2))


@app.command("temporal-diff")
def temporal_diff_command(
    repo_path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    before: str = typer.Argument(..., help="Before git ref/commit."),
    after: str = typer.Argument(..., help="After git ref/commit."),
) -> None:
    """Phase 9: deterministic architecture diff between two commits."""

    diff = architecture_diff(repo_path.resolve(), before, after)
    typer.echo(diff.model_dump_json(indent=2))


@app.command("temporal-metrics")
def temporal_metrics_command(
    repo_path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    max_commits: int = typer.Option(25, "--max-commits", help="Maximum commits to include."),
    since: str | None = typer.Option(None, "--since", help="Optional git --since value."),
    out: Path | None = typer.Option(None, "--out", help="Output JSON path. Defaults to .heart-transplant/reports/<timestamp>__phase-9-temporal-metrics.json."),
) -> None:
    """Phase 9: deterministic time-series architecture metrics."""

    report = temporal_metrics(repo_path.resolve(), max_commits=max_commits, since=since)
    dest = write_temporal_metrics(report, out.resolve() if out else None)
    typer.echo(json.dumps({"wrote": str(dest), "commit_count": report.commit_count, "block_churn_rate": report.block_churn_rate}, indent=2))


@app.command("persist-temporal-surreal")
def persist_temporal_surreal_command(
    repo_path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    max_commits: int = typer.Option(25, "--max-commits", help="Maximum commits to include."),
    since: str | None = typer.Option(None, "--since", help="Optional git date expression passed to git log."),
) -> None:
    """Phase 9: persist temporal snapshots, diffs, and summary rows into SurrealDB."""

    report = temporal_metrics(repo_path.resolve(), max_commits=max_commits, since=since)
    result = persist_temporal_metrics(report)
    typer.echo(json.dumps(result, indent=2))


@app.command("temporal-drift")
def temporal_drift_command(
    repo_path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    before: str = typer.Argument(..., help="Before git ref/commit."),
    after: str = typer.Argument(..., help="After git ref/commit."),
    expected_path: list[str] | None = typer.Option(None, "--expected-path", help="Optional expected drift path for scoring; may be repeated."),
) -> None:
    """Phase 9: detect file-level block-membership drift between two commits."""

    report = detect_architectural_drift(
        repo_path.resolve(),
        before,
        after,
        expected_paths=set(expected_path or []) if expected_path else None,
    )
    typer.echo(report.model_dump_json(indent=2))


@app.command("temporal-gates")
def temporal_gates_command(
    repo_path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    max_commits: int = typer.Option(25, "--max-commits", help="Maximum commits to include in reproducibility/known-change gates."),
    expected_changes: Path | None = typer.Option(None, "--expected-changes", exists=True, dir_okay=False, help="JSON list of {after_sha,path,status} expected changes."),
    drift_before: str | None = typer.Option(None, "--drift-before", help="Before ref for drift gate."),
    drift_after: str | None = typer.Option(None, "--drift-after", help="After ref for drift gate."),
    expected_drift_path: list[str] | None = typer.Option(None, "--expected-drift-path", help="Expected drift path; may be repeated."),
) -> None:
    """Phase 9 gates: exact known changes, drift scoring, and reproducibility."""

    expected = json.loads(expected_changes.read_text(encoding="utf-8")) if expected_changes else None
    report = run_temporal_gates(
        repo_path.resolve(),
        max_commits=max_commits,
        expected_changes=expected,
        drift_before=drift_before,
        drift_after=drift_after,
        expected_drift_paths=set(expected_drift_path or []) if expected_drift_path else None,
    )
    typer.echo(json.dumps(report, indent=2))
    if report["summary"]["overall_status"] != "pass":
        raise typer.Exit(code=1)


@app.command("simulate-change")
def simulate_change_command(
    change: str = typer.Argument(..., help="Natural-language change hypothesis."),
    artifact_dir: Path | None = typer.Option(
        None,
        "--artifact-dir",
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Structural artifact directory. Defaults to latest under .heart-transplant/artifacts.",
    ),
    temporal_report: Path | None = typer.Option(
        None,
        "--temporal-report",
        exists=True,
        dir_okay=False,
        help="Optional Phase 9 temporal-scan JSON for file hotspot boosting.",
    ),
    confidence_threshold: float = typer.Option(0.7, "--confidence-threshold", help="Report threshold note in limitations."),
    seed: int = typer.Option(42, "--seed", help="RNG seed for Monte Carlo runs."),
    mc_runs: int = typer.Option(64, "--mc-runs", help="Number of Monte Carlo rollouts."),
) -> None:
    """Phase 10: Monte Carlo structural impact simulation (auditable trace, no LLM)."""

    chosen = artifact_dir.resolve() if artifact_dir else latest_artifact_dir()
    result = run_change_simulation(
        change,
        chosen,
        temporal_report_path=temporal_report.resolve() if temporal_report else None,
        rng_seed=seed,
        mc_runs=mc_runs,
        confidence_threshold=confidence_threshold,
    )
    typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=True))


@app.command("regret-scan")
def regret_scan_command(
    artifact_dir: Path | None = typer.Option(
        None,
        "--artifact-dir",
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Defaults to latest artifact directory.",
    ),
    min_confidence: float = typer.Option(0.35, "--min-confidence", help="Minimum regret score to emit."),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Also write full JSON report to this path (for execute-transplant --plan).",
    ),
) -> None:
    """Phase 11: heuristic regret surface + surgery plans."""

    chosen = artifact_dir.resolve() if artifact_dir else latest_artifact_dir()
    report = run_regret_scan(chosen, min_confidence=min_confidence)
    if output:
        write_json(output.resolve(), report.model_dump(mode="json"))
    typer.echo(report.model_dump_json(indent=2))


@app.command("regret-sdk-scan")
def regret_sdk_scan_command(
    artifact_dir: Path | None = typer.Option(
        None,
        "--artifact-dir",
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Defaults to latest artifact directory.",
    ),
    min_confidence: float = typer.Option(0.35, "--min-confidence", help="Minimum regret score to emit."),
    output: Path | None = typer.Option(
        None,
        "--output",
        help="Also write stable SDK JSON to this path.",
    ),
) -> None:
    """Regret SDK contract: ranked surfaces with evidence, plan, simulation, and ledger fields."""

    chosen = artifact_dir.resolve() if artifact_dir else latest_artifact_dir()
    report = run_regret_sdk_scan(chosen, min_confidence=min_confidence)
    if output:
        write_json(output.resolve(), report.model_dump(mode="json"))
    typer.echo(report.model_dump_json(indent=2))


@app.command("execute-transplant")
def execute_transplant_command(
    regret_id: str = typer.Argument(..., help="Identifier from a regret / surgery plan."),
    artifact_dir: Path | None = typer.Option(
        None,
        "--artifact-dir",
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Artifact directory (for repo path). Defaults to latest.",
    ),
    plan: Path | None = typer.Option(
        None,
        "--plan",
        exists=True,
        dir_okay=False,
        help="JSON from `regret-scan --output`.",
    ),
    execute: bool = typer.Option(
        False,
        "--execute",
        help="If set, runs compileall validation after logging intent (no automatic patches).",
    ),
) -> None:
    """Phase 12: transplant planner + ledger (does not rewrite source files)."""

    chosen = artifact_dir.resolve() if artifact_dir else latest_artifact_dir()
    result = run_transplant(
        regret_id,
        chosen,
        plan_path=plan.resolve() if plan else None,
        dry_run=not execute,
    )
    typer.echo(result.model_dump_json(indent=2))


@app.command("multimodal-ingest")
def multimodal_ingest_command(
    directory: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    include_tests: bool = typer.Option(True, "--include-tests/--no-include-tests"),
    include_infra: bool = typer.Option(True, "--include-infra/--no-include-infra"),
    out: Path | None = typer.Option(
        None,
        "--out",
        help="Output JSON path (default: .heart-transplant/reports/<timestamp>__multimodal-ingest.json).",
    ),
) -> None:
    """Phase 13: correlate tests, openapi.json, and infra files to source tree."""

    report = run_multimodal_ingest(
        directory.resolve(),
        include_tests=include_tests,
        include_infra=include_infra,
        write_artifact=out.resolve() if out else None,
    )
    typer.echo(report.model_dump_json(indent=2))


@app.command("program-surface")
def program_surface_command() -> None:
    """Phase 14: JSON index of phase module readiness (imports + symbols)."""

    typer.echo(json.dumps(program_surface_status(), indent=2))


@app.command("logiclens-demo")
def logiclens_demo_command(
    target: Path = typer.Argument(..., exists=True, help="Repo directory or existing artifact directory."),
    repo_name: str | None = typer.Option(None, "--repo-name", help="Override repo name when ingesting."),
    out_dir: Path | None = typer.Option(None, "--out-dir", help="Demo packet directory (default: <artifact>/demo)."),
    with_scip: bool = typer.Option(False, "--with-scip", help="Run scip-typescript when target is a TS/JS repo."),
    install_deps: bool = typer.Option(False, "--install-deps", help="Install Node deps before SCIP when needed."),
    use_openai: bool = typer.Option(False, "--use-openai", help="Use OpenAI during classification if OPENAI_API_KEY is set."),
    mc_runs: int = typer.Option(32, "--mc-runs", help="Monte Carlo runs for blast-radius simulations."),
    min_regret_confidence: float = typer.Option(0.35, "--min-regret-confidence"),
) -> None:
    """Run the launchable end-to-end LogicLens demonstration on a repo or artifact."""

    result = run_logiclens_demo(
        target.resolve(),
        repo_name=repo_name,
        out_dir=out_dir.resolve() if out_dir else None,
        with_scip=with_scip,
        install_deps=install_deps,
        use_openai=use_openai,
        mc_runs=mc_runs,
        min_regret_confidence=min_regret_confidence,
    )
    typer.echo(json.dumps(result, indent=2))


if __name__ == "__main__":
    app()
