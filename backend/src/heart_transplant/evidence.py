from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from pathlib import Path
import re
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from heart_transplant.artifact_store import read_json
from heart_transplant.blast_radius import compute_impact_subgraph
from heart_transplant.evals.gold_benchmark import build_block_benchmark_report, load_gold_set

"""Evidence bundles for LogicLens-style retrieval (artifact-backed)."""

# Codes-tool lexical normalization / abstention — see docs/evals/codes_tool_calibration.md
DEFAULT_CODES_MIN_SCORE: float = 0.12
CODES_CONFIDENCE_INTERCEPT: float = 0.35
CODES_CONFIDENCE_SLOPE: float = 0.55
NORMALIZED_LEXICAL_DENOM_BIAS: float = 3.0


class EvidenceNode(BaseModel):
    node_id: str
    kind: str
    file_path: str | None = None
    range: dict[str, int] | None = None
    label: str | None = None
    snippet: str | None = None


class SourceExcerpt(BaseModel):
    """Inline source cited by an evidence bundle (Source-tool parity without a second round-trip)."""

    node_id: str
    file_path: str | None = None
    range: dict[str, int] | None = None
    text: str


class EvidencePath(BaseModel):
    node_ids: list[str] = Field(default_factory=list)
    edge_types: list[str] = Field(default_factory=list)
    edge_provenance: list[str | None] = Field(default_factory=list)
    """Parallel to hops in ``edge_types`` (``None`` when unknown)."""
    edge_direction: list[Literal["out", "in"]] = Field(default_factory=list)
    """Per hop: ``out`` when traversing source→target as stored; ``in`` when traversing target→source."""


class EvidenceBundle(BaseModel):
    query_type: str
    claim: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_nodes: list[EvidenceNode] = Field(default_factory=list)
    file_ranges: list[dict[str, Any]] = Field(default_factory=list)
    paths: list[EvidencePath] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    """Structured gaps (coverage, depth, summaries) distinct from operational caveats."""
    source_excerpts: list[SourceExcerpt] = Field(default_factory=list)
    """Full cited excerpts for reviewers (Source-tool shaped)."""

    @model_validator(mode="after")
    def _confidence_requires_evidence(self) -> EvidenceBundle:
        """Gate: positive confidence must carry node or path receipts."""
        if self.confidence > 0 and not self.source_nodes and not self.paths:
            raise ValueError("EvidenceBundle: confidence>0 requires source_nodes or paths")
        return self


@dataclass(frozen=True)
class QuestionIntent:
    blocks: tuple[str, ...]
    keywords: tuple[str, ...]
    requires_trace: bool = False


_BLOCK_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Access Control": ("auth", "access", "permission", "role", "guard", "jwt", "session", "user"),
    "Identity UI": ("identity", "login", "signin", "profile", "account"),
    "Data Persistence": ("database", "db", "schema", "model", "migration", "prisma", "drizzle", "sql", "redis", "store"),
    "Persistence Strategy": ("cache", "redis", "store"),
    "Network Edge": ("route", "http", "request", "response", "endpoint", "middleware", "webhook", "server"),
    "Background Processing": ("queue", "worker", "job", "cron", "schedule", "background", "async"),
    "System Telemetry": ("log", "logger", "telemetry", "metric", "tracing", "observability", "sentry", "otel"),
    "Security Ops": ("secret", "encrypt", "decrypt", "hash", "csrf", "cors", "key", "token"),
    "Core Rendering": ("render", "component", "ui", "view", "page", "screen"),
    "Global Interface": ("config", "configuration", "environment", "env", "settings"),
}

_CODES_RANK_QUERY_STOP: frozenset[str] = frozenset(
    {
        "repo",
        "repository",
        "function",
        "functions",
        "method",
        "methods",
        "class",
        "classes",
        "symbol",
        "symbols",
        "code",
        "source",
        "file",
        "files",
        "path",
        "paths",
        "snippet",
        "implementation",
        "implementations",
        "contain",
        "contains",
        "exported",
        "export",
        "exports",
        "define",
        "defines",
        "body",
        "locate",
        "locating",
        "find",
        "finding",
        "using",
        "based",
        "typescript",
        "javascript",
    }
)

# Expand routing-query vocabulary for lexical retrieval (projects / incident ranking).
_RETRIEVAL_TERM_EXPANSION: dict[str, frozenset[str]] = {
    "database": frozenset({"database", "db", "persist", "persistence", "storage", "sql", "query"}),
    "persist": frozenset({"persist", "persistence", "database", "db", "storage"}),
    "persistence": frozenset({"persist", "persistence", "database", "db", "storage"}),
    "storage": frozenset({"storage", "database", "db", "persist", "persistence"}),
    "session": frozenset({"session", "sessions", "sessionguard"}),
    "sessions": frozenset({"session", "sessions", "sessionguard"}),
    "component": frozenset({"component", "components", "service", "module", "file"}),
    "components": frozenset({"component", "components", "service", "module", "file"}),
    "service": frozenset({"service", "services", "component", "module"}),
}


def explain_node(artifact_dir: Path, node_id: str) -> EvidenceBundle:
    graph = _load_graph(artifact_dir)
    node = graph["nodes_by_id"].get(node_id)
    if not node:
        return EvidenceBundle(
            query_type="explain_node",
            claim=f"No node found for {node_id}",
            confidence=0.0,
            limitations=["node_id was not present in structural artifact"],
        )
    neighbors = _incident_edges(graph, node_id)
    excerpts = _source_excerpts_for_nodes(graph, [node])
    return EvidenceBundle(
        query_type="explain_node",
        claim=f"{node_id} is a {node.get('kind')} surface in {node.get('file_path') or 'the graph'}.",
        confidence=0.75,
        source_nodes=[_evidence_node(node)],
        file_ranges=_file_ranges([node]),
        paths=[EvidencePath(node_ids=[node_id], edge_types=[])],
        limitations=[f"{len(neighbors)} incident edges were found; semantic confidence depends on classifier output."],
        source_excerpts=excerpts,
    )


def explain_file(artifact_dir: Path, file_path: str) -> EvidenceBundle:
    graph = _load_graph(artifact_dir)
    nodes = [node for node in graph["nodes_by_id"].values() if node.get("file_path") == file_path]
    if not nodes:
        return EvidenceBundle(
            query_type="explain_file",
            claim=f"No graph nodes found for {file_path}",
            confidence=0.0,
            limitations=["file was not materialized as a FileNode or CodeNode"],
        )
    blocks = _semantic_blocks(artifact_dir, [str(node["node_id"]) for node in nodes])
    label = ", ".join(sorted(set(blocks.values()))) if blocks else "unclassified"
    return EvidenceBundle(
        query_type="explain_file",
        claim=f"{file_path} has {len(nodes)} graph node(s) and block evidence: {label}.",
        confidence=0.7 if blocks else 0.45,
        source_nodes=[_evidence_node(node) for node in nodes[:20]],
        file_ranges=_file_ranges(nodes[:20]),
        limitations=[] if blocks else ["semantic-artifact.json missing or no block assignment for this file"],
    )


def trace_dependency(artifact_dir: Path, start_id: str, end_id: str, *, max_depth: int = 6) -> EvidenceBundle:
    graph = _load_graph(artifact_dir)
    path = _bfs_path(graph, start_id, end_id, max_depth=max_depth, directed=True)
    if not path:
        return EvidenceBundle(
            query_type="trace_dependency",
            claim=f"No dependency path found from {start_id} to {end_id} within depth {max_depth}.",
            confidence=0.0,
            limitations=["absence of a path may reflect incomplete extraction or SCIP fallback gaps"],
        )
    nodes = [graph["nodes_by_id"].get(node_id) for node_id in path["node_ids"]]
    return EvidenceBundle(
        query_type="trace_dependency",
        claim=f"Found path of {len(path['edge_types'])} edge(s) from {start_id} to {end_id}.",
        confidence=0.85,
        source_nodes=[_evidence_node(node) for node in nodes if node],
        file_ranges=_file_ranges([node for node in nodes if node]),
        paths=[
            EvidencePath(
                node_ids=path["node_ids"],
                edge_types=path["edge_types"],
                edge_provenance=path.get("edge_provenance", []),
                edge_direction=path.get("edge_direction", []),
            )
        ],
    )


def find_architectural_block(artifact_dir: Path, block_label: str, *, limit: int = 50) -> EvidenceBundle:
    sem = _load_semantic(artifact_dir)
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    nodes_by_id = _nodes_by_id(structural)
    matches = []
    for row in sem.get("block_assignments", []):
        secondary = [item.get("block") for item in row.get("secondary_blocks", []) if isinstance(item, dict)]
        if row.get("primary_block") == block_label or block_label in secondary:
            node = nodes_by_id.get(str(row.get("node_id", "")))
            if node:
                matches.append(node)
    return EvidenceBundle(
        query_type="find_architectural_block",
        claim=f"Found {len(matches)} node(s) assigned to {block_label}.",
        confidence=0.75 if matches else 0.35,
        source_nodes=[_evidence_node(node) for node in matches[:limit]],
        file_ranges=_file_ranges(matches[:limit]),
        limitations=[] if sem else ["semantic-artifact.json missing"],
    )


def query_entities(artifact_dir: Path, query: str, *, limit: int = 20) -> EvidenceBundle:
    """Artifact-backed approximation of the paper's Entities Tool."""

    sem = _load_semantic(artifact_dir)
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    graph = _load_graph(artifact_dir)
    actions_by_entity: dict[str, list[dict[str, Any]]] = {}
    for action in sem.get("actions", []) or []:
        actions_by_entity.setdefault(str(action.get("entity_id")), []).append(action)

    scored: list[tuple[float, dict[str, Any]]] = []
    for entity in sem.get("entities", []) or []:
        score = _text_score(query, " ".join(str(entity.get(key) or "") for key in ("name", "category", "description")))
        if score > 0:
            scored.append((score + min(len(actions_by_entity.get(str(entity.get("entity_id")), [])), 5) * 0.2, entity))
    scored.sort(key=lambda item: (-item[0], str(item[1].get("name") or "")))
    selected = [entity for _score, entity in scored[:limit]]

    code_nodes: list[dict[str, Any]] = []
    for entity in selected:
        for action in actions_by_entity.get(str(entity.get("entity_id")), []):
            node = graph["nodes_by_id"].get(str(action.get("source_code_node_id")))
            if node:
                code_nodes.append(node)

    if not selected:
        return EvidenceBundle(
            query_type="query_entities",
            claim=f"No semantic entities matched query: {query}",
            confidence=0.2 if sem else 0.0,
            limitations=["semantic-artifact.json missing or no entity text matched the query"] if not sem else ["no entity matched the query"],
        )

    project = structural.get("project_node") or {}
    return EvidenceBundle(
        query_type="query_entities",
        claim=(
            f"Matched {len(selected)} semantic entit(y/ies) for '{query}' in project "
            f"{project.get('name') or structural.get('repo_name')}."
        ),
        confidence=min(0.55 + len(code_nodes[:5]) * 0.05, 0.85),
        source_nodes=[_evidence_node(node) for node in _dedupe_nodes(code_nodes)[:limit]],
        file_ranges=_file_ranges(_dedupe_nodes(code_nodes)[:limit]),
        paths=[
            EvidencePath(
                node_ids=[str(action.get("source_code_node_id")), str(action.get("entity_id"))],
                edge_types=[str(action.get("action") or "ACTION")],
                edge_provenance=[None],
                edge_direction=["out"],
            )
            for entity in selected
            for action in actions_by_entity.get(str(entity.get("entity_id")), [])[:3]
        ][:limit],
        limitations=[],
    )


def query_codes(
    artifact_dir: Path,
    query: str,
    *,
    limit: int = 20,
    subgraph_depth: int = 3,
    subgraph_max_edges: int = 120,
    min_score: float = DEFAULT_CODES_MIN_SCORE,
) -> EvidenceBundle:
    """Paper Codes Tool: rank symbol/code nodes, expand a bounded connected subgraph, attach provenance."""

    graph = _load_graph(artifact_dir)
    sem = _load_semantic(artifact_dir)
    summary_by_node = {
        str(row.get("node_id")): str(row.get("text") or "")
        for row in sem.get("semantic_summaries", []) or []
        if row.get("summary_type") == "code_node" and row.get("node_id")
    }
    semantic_rows = _semantic_rows_by_node(artifact_dir)

    def is_rankable_code_surface(node: dict[str, Any]) -> bool:
        kind = str(node.get("kind") or "").lower()
        if kind in {"project", "system", "file"}:
            return False
        if kind == "file_surface":
            return False
        sym_src = str(node.get("symbol_source") or "")
        if sym_src == "file_surface":
            return False
        return bool(node.get("file_path") or node.get("name"))

    ranked_pairs: list[tuple[float, dict[str, Any]]] = []
    for node in graph["nodes_by_id"].values():
        if not is_rankable_code_surface(node):
            continue
        node_id = str(node.get("node_id") or node.get("scip_id") or "")
        row = semantic_rows.get(node_id)
        extra = " ".join(
            [
                summary_by_node.get(node_id, ""),
                str(row.get("reasoning") or "") if row else "",
                str(row.get("primary_block") or "") if row else "",
            ]
        )
        haystack = " ".join(
            str(part or "")
            for part in [
                node.get("repo_name"),
                node.get("file_path"),
                node.get("name"),
                node.get("kind"),
                node.get("content"),
                extra,
            ]
        )
        score = _normalized_lexical_score_for_codes(query, haystack)
        if score > 0:
            ranked_pairs.append((score, node))
    ranked_pairs.sort(
        key=lambda item: (
            -item[0],
            _is_test_path(str(item[1].get("file_path") or "")),
            str(item[1].get("file_path") or ""),
        )
    )

    chosen_pairs: list[tuple[float, dict[str, Any]]] = []
    seen_ids: set[str] = set()
    for score, node in ranked_pairs:
        nid = str(node.get("node_id") or node.get("scip_id") or "")
        if not nid or nid in seen_ids:
            continue
        seen_ids.add(nid)
        chosen_pairs.append((score, node))
        if len(chosen_pairs) >= limit:
            break

    chosen = [node for _s, node in chosen_pairs]
    top_score = chosen_pairs[0][0] if chosen_pairs else 0.0

    if not chosen:
        return EvidenceBundle(
            query_type="query_codes",
            claim=f"No code symbol nodes matched query: {query}",
            confidence=0.0,
            limitations=[
                "no code symbol matched the query above the abstention threshold; "
                "try broader keywords or verify ingest/classifier coverage",
            ],
        )

    if top_score < min_score:
        return EvidenceBundle(
            query_type="query_codes",
            claim=f"Insufficient lexical relevance for query: {query} (best score {top_score:.3f} < {min_score}).",
            confidence=0.0,
            limitations=[
                f"best_rank_score={top_score:.3f}; abstaining from ranking garbage matches",
            ],
        )

    seeds_list = [str(n.get("node_id") or n.get("scip_id")) for n in chosen[: min(8, len(chosen))]]
    seeds = set(seeds_list)
    path_bundle = _codes_tool_subgraph_paths(
        graph,
        seeds_list,
        max_depth=subgraph_depth,
        max_edges=subgraph_max_edges,
    )

    missing_evidence: list[str] = []
    without_summary = sum(
        1 for nid in (str(n.get("node_id") or n.get("scip_id")) for n in chosen) if not summary_by_node.get(nid)
    )
    if without_summary:
        missing_evidence.append(f"no semantic code_node summary for {without_summary}/{len(chosen)} ranked symbol(s)")
    deep_paths = [p for p in path_bundle if len(p.edge_types) >= 2]
    if not deep_paths:
        missing_evidence.append(f"no subgraph walk reached depth >= 2 within depth_cap={subgraph_depth}")
    elif not any(len(p.edge_types) >= 2 and any(d is not None for d in p.edge_provenance) for p in deep_paths):
        missing_evidence.append("no hop carried structural edge provenance (treesitter-only artifact)")

    conf = round(min(CODES_CONFIDENCE_INTERCEPT + CODES_CONFIDENCE_SLOPE * top_score, 0.92), 3)
    limitations = [
        f"codes subgraph: seeds={len(seeds)}, depth={subgraph_depth}, structural_paths_emitted={len(path_bundle)}",
        "expanded along stored edge direction (out from source_id); CALLS/REFERENCES topology",
    ]

    excerpts = _source_excerpts_for_nodes(graph, chosen[: min(15, len(chosen))])

    return EvidenceBundle(
        query_type="query_codes",
        claim=(
            f"Codes retrieval for '{query}': top_rank_score={top_score:.3f} (post-dedupe); "
            f"{len(chosen)} ranked symbol(s); paths={len(path_bundle)}."
        ),
        confidence=conf,
        source_nodes=[_evidence_node(node) for node in chosen],
        file_ranges=_file_ranges(chosen),
        paths=path_bundle,
        limitations=limitations,
        missing_evidence=missing_evidence,
        source_excerpts=excerpts,
    )


def query_projects(artifact_dir: Path, query: str, *, limit: int = 20) -> EvidenceBundle:
    """Artifact-backed approximation of the paper's Projects Tool."""

    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    sem = _load_semantic(artifact_dir)
    project = structural.get("project_node") or {}
    summaries = [
        row
        for row in sem.get("semantic_summaries", []) or []
        if row.get("summary_type") in {"project", "system"}
    ]
    score = _text_score(
        query,
        " ".join(
            [
                str(project.get("name") or ""),
                str(structural.get("repo_name") or ""),
                *(str(row.get("text") or "") for row in summaries),
            ]
        ),
    )
    nodes = _rank_nodes_by_text(_load_graph(artifact_dir), query, limit=limit, artifact_dir=artifact_dir)
    if score <= 0 and not nodes:
        return EvidenceBundle(
            query_type="query_projects",
            claim=f"No project evidence matched query: {query}",
            confidence=0.0,
            limitations=["project summary and code surfaces did not match the query"],
        )
    if not nodes:
        return EvidenceBundle(
            query_type="query_projects",
            claim=f"No code surfaces matched query: {query}",
            confidence=0.0,
            limitations=[
                "project or repo metadata matched weakly, but no ranked code/file nodes matched the query text",
            ],
        )
    return EvidenceBundle(
        query_type="query_projects",
        claim=f"Project {project.get('name') or structural.get('repo_name')} matched '{query}' with {len(nodes)} supporting node(s).",
        confidence=min(0.55 + score * 0.05 + len(nodes[:5]) * 0.03, 0.85),
        source_nodes=[_evidence_node(node) for node in nodes],
        file_ranges=_file_ranges(nodes),
        paths=[EvidencePath(node_ids=["system:local", str(project.get("node_id"))], edge_types=["CONTAINS"])] if project.get("node_id") else [],
        limitations=[] if summaries else ["semantic project/system summaries are missing"],
    )


def trace_entity_workflow(artifact_dir: Path, entity_query: str, *, limit: int = 30) -> EvidenceBundle:
    """Trace code nodes that act on matching entities, ordered by semantic action."""

    bundle = query_entities(artifact_dir, entity_query, limit=limit)
    if not bundle.paths:
        bundle.query_type = "trace_entity_workflow"
        return bundle
    ordered = sorted(bundle.paths, key=lambda path: (_workflow_action_rank(path.edge_types[0] if path.edge_types else ""), path.node_ids))
    bundle.query_type = "trace_entity_workflow"
    bundle.claim = f"Workflow evidence for '{entity_query}' spans {len(ordered)} semantic action edge(s)."
    bundle.paths = ordered[:limit]
    if len(bundle.source_nodes) > 1 and not bundle.limitations:
        bundle.limitations.append("Ordering is inferred from action labels; runtime sequence is not proven without traces.")
    return bundle


def impact_radius(artifact_dir: Path, start_id: str, *, max_depth: int = 3, max_nodes: int = 100) -> EvidenceBundle:
    try:
        impact = compute_impact_subgraph(start_id, max_depth=max_depth, max_nodes=max_nodes)
        return EvidenceBundle(
            query_type="impact_radius",
            claim=f"Impact radius from {start_id} reached {impact.get('node_count', 0)} node(s).",
            confidence=0.65,
            paths=[EvidencePath(node_ids=list(impact.get("nodes", [])), edge_types=[])],
            limitations=["impact_radius currently uses the configured graph DB; artifact_dir is retained for API symmetry"],
        )
    except Exception as exc:  # noqa: BLE001
        return EvidenceBundle(
            query_type="impact_radius",
            claim=f"Impact radius could not run for {start_id}.",
            confidence=0.0,
            limitations=[str(exc)],
        )


def answer_with_evidence(artifact_dir: Path, question: str) -> EvidenceBundle:
    # Domain entity / workflow questions before block-intent routing so words like "user"
    # do not send the prompt only to Access Control block evidence.
    if re.search(r"\b(entity|entities|workflow|flow|creation|activation|delete|deletion|produce|configure)\b", question, re.I):
        return trace_entity_workflow(artifact_dir, question)
    q = question.lower()
    has_project = bool(re.search(r"\b(project|repo|repository|service|services|component|components)\b", question, re.I))
    has_codes = bool(
        re.search(
            r"\b(code|source code|sourcecode|function|functions|class|classes|method|methods|symbol|symbols|implementation|implemented|implements|snippet|source|file|files|path|paths|export|exports|define|defines|contains|containing|body|locate|locating|find|finding|logic|written)\b",
            question,
            re.I,
        )
    )
    if has_project and has_codes:
        codes_bundle = query_codes(artifact_dir, question)
        if not codes_bundle.source_nodes:
            codes_bundle = query_codes(artifact_dir, question, min_score=0.05)
        return _merge_project_codes_bundles(query_projects(artifact_dir, question), codes_bundle)
    if has_codes and not re.search(r"\b(project|repo|repository|service|services|component|components)\b", q):
        return query_codes(artifact_dir, question)
    if has_project:
        return query_projects(artifact_dir, question)
    intent = _plan_question(question)
    if intent.blocks:
        return _answer_from_ranked_evidence(artifact_dir, question, intent)
    return EvidenceBundle(
        query_type="unsupported",
        claim="Insufficient evidence to answer this architecture question with the current deterministic router.",
        confidence=0.0,
        limitations=["question router could not map the prompt onto a supported architecture block"],
    )


def benchmark_with_evidence(artifact_dir: Path, gold_set: Path) -> dict[str, Any]:
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    return build_block_benchmark_report(
        structural,
        load_gold_set(gold_set),
        artifact_dir=Path(artifact_dir),
        gold_set_path=gold_set,
    )


def _load_graph(artifact_dir: Path) -> dict[str, Any]:
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    return {"structural": structural, "nodes_by_id": _nodes_by_id(structural)}


def _nodes_by_id(structural: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes: dict[str, dict[str, Any]] = {}
    project = structural.get("project_node") or {}
    if project.get("node_id"):
        nodes[str(project["node_id"])] = {"node_id": project["node_id"], "kind": "project", **project}
    for node in structural.get("file_nodes", []):
        nodes[str(node["node_id"])] = {"kind": "file", **node}
    for node in structural.get("code_nodes", []):
        nodes[str(node.get("node_id") or node.get("scip_id"))] = {"node_id": node.get("node_id") or node.get("scip_id"), **node}
    return nodes


def _load_semantic(artifact_dir: Path) -> dict[str, Any]:
    path = Path(artifact_dir) / "semantic-artifact.json"
    return read_json(path) if path.is_file() else {}


def _semantic_rows_by_node(artifact_dir: Path) -> dict[str, dict[str, Any]]:
    sem = _load_semantic(artifact_dir)
    return {str(row.get("node_id")): row for row in sem.get("block_assignments", []) if row.get("node_id")}


def _semantic_blocks(artifact_dir: Path, node_ids: list[str]) -> dict[str, str]:
    sem = _load_semantic(artifact_dir)
    wanted = set(node_ids)
    return {
        str(row.get("node_id")): str(row.get("primary_block"))
        for row in sem.get("block_assignments", [])
        if str(row.get("node_id")) in wanted and row.get("primary_block")
    }


def _codes_query_terms(query: str) -> list[str]:
    terms = _terms(query)
    out: list[str] = []
    seen: set[str] = set()
    for t in terms:
        bucket = {t, *_RETRIEVAL_TERM_EXPANSION.get(t, ())}
        for u in bucket:
            if u in _CODES_RANK_QUERY_STOP:
                continue
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out


def _normalized_lexical_score_for_codes(query: str, haystack: str) -> float:
    """Lexical rank for Codes Tool: strips boilerplate query tokens so garbage prompts abstain."""
    qt = _codes_query_terms(query)
    if not qt:
        return 0.0
    hay = haystack.lower()
    raw = sum(1.0 for term in qt if term in hay)
    phrase = query.strip().lower()
    if phrase and phrase in hay:
        raw += 3.0
    denom = max(len(qt), 1) + NORMALIZED_LEXICAL_DENOM_BIAS
    return min(raw / denom, 1.0)


def _incident_edges(graph: dict[str, Any], node_id: str) -> list[dict[str, Any]]:
    return [
        edge
        for edge in graph["structural"].get("edges", [])
        if edge.get("source_id") == node_id or edge.get("target_id") == node_id
    ]


def _bfs_path(
    graph: dict[str, Any],
    start_id: str,
    end_id: str,
    *,
    max_depth: int,
    directed: bool = True,
) -> dict[str, list[str]] | None:
    edges = graph["structural"].get("edges", [])
    adjacency: dict[str, list[tuple[str, str, str | None, Literal["out", "in"]]]] = {}
    for edge in edges:
        s = str(edge.get("source_id"))
        t = str(edge.get("target_id"))
        et = str(edge.get("edge_type"))
        prov_raw = edge.get("provenance")
        prov = str(prov_raw) if prov_raw is not None else None
        adjacency.setdefault(s, []).append((t, et, prov, "out"))
        if not directed:
            adjacency.setdefault(t, []).append((s, et, prov, "in"))
    queue = deque([(start_id, [start_id], [], [], [])])
    seen = {start_id}
    while queue:
        node_id, path, edge_types, provs, dirs = queue.popleft()
        if node_id == end_id:
            return {"node_ids": path, "edge_types": edge_types, "edge_provenance": provs, "edge_direction": dirs}
        if len(edge_types) >= max_depth:
            continue
        for nxt, edge_type, p, d in adjacency.get(node_id, []):
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append((nxt, [*path, nxt], [*edge_types, edge_type], [*provs, p], [*dirs, d]))
    return None


def _evidence_node(node: dict[str, Any]) -> EvidenceNode:
    return EvidenceNode(
        node_id=str(node.get("node_id") or node.get("scip_id")),
        kind=str(node.get("kind", "")),
        file_path=node.get("file_path"),
        range=node.get("range") if isinstance(node.get("range"), dict) else None,
        label=str(node.get("name")) if node.get("name") else None,
        snippet=_snippet(node),
    )


def _full_source_text(node: dict[str, Any]) -> str:
    return str(node.get("content") or "").strip()


def _source_excerpts_for_nodes(graph: dict[str, Any], nodes: list[dict[str, Any]]) -> list[SourceExcerpt]:
    """Inline Source-tool excerpts from structural node content."""
    excerpts: list[SourceExcerpt] = []
    for node in nodes:
        text = _full_source_text(node)
        if not text:
            continue
        nid = str(node.get("node_id") or node.get("scip_id"))
        raw = text
        cap = 12000
        if len(raw) > cap:
            raw = raw[:cap] + "\n/* truncated */"
        excerpts.append(
            SourceExcerpt(
                node_id=nid,
                file_path=node.get("file_path"),
                range=node.get("range") if isinstance(node.get("range"), dict) else None,
                text=raw,
            )
        )
    return excerpts


def _merge_project_codes_bundles(project_bundle: EvidenceBundle, codes_bundle: EvidenceBundle) -> EvidenceBundle:
    """Hybrid retrieval: project context plus code-centric subgraph (explicit precedence)."""
    seen: set[str] = set()
    merged_nodes: list[EvidenceNode] = []
    for node in [*project_bundle.source_nodes, *codes_bundle.source_nodes]:
        if node.node_id in seen:
            continue
        seen.add(node.node_id)
        merged_nodes.append(node)
    conf = round(min(0.92, (project_bundle.confidence + codes_bundle.confidence) / 2), 3)
    excerpts: list[SourceExcerpt] = []
    ex_seen: set[str] = set()
    for ex in [*project_bundle.source_excerpts, *codes_bundle.source_excerpts]:
        if ex.node_id in ex_seen:
            continue
        ex_seen.add(ex.node_id)
        excerpts.append(ex)
    return EvidenceBundle(
        query_type="query_projects_with_codes",
        claim=f"{project_bundle.claim} | {codes_bundle.claim}",
        confidence=conf,
        source_nodes=merged_nodes,
        file_ranges=[*project_bundle.file_ranges, *codes_bundle.file_ranges],
        paths=[*project_bundle.paths, *codes_bundle.paths],
        limitations=[
            "hybrid bundle: query_projects + query_codes for project+codes prompts",
            *project_bundle.limitations,
            *codes_bundle.limitations,
        ],
        missing_evidence=[*project_bundle.missing_evidence, *codes_bundle.missing_evidence],
        source_excerpts=excerpts,
    )


def _file_ranges(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for node in nodes:
        if node.get("file_path") and isinstance(node.get("range"), dict):
            out.append({"file_path": node["file_path"], "range": node["range"], "node_id": node.get("node_id") or node.get("scip_id")})
    return out


def _plan_question(question: str) -> QuestionIntent:
    q = question.lower()
    blocks: list[str] = []
    keywords: list[str] = []

    def add(block: str, *terms: str) -> None:
        if block not in blocks:
            blocks.append(block)
        for term in terms:
            if term not in keywords:
                keywords.append(term)

    if re.search(r"\b(auth|authentication|authenticate|access|permission|role|rbac|guard|jwt|session|identity|user)\b", q):
        add("Access Control", "auth", "access", "permission", "role", "guard", "jwt", "session", "user")
    if re.search(r"\b(identity ui|login|sign[- ]?in|profile|account)\b", q):
        add("Identity UI", "identity", "login", "signin", "profile", "account")
    if re.search(r"\b(database|db|persistence|persist|storage|schema|model|migration|prisma|drizzle|sql|redis|store)\b", q):
        add("Data Persistence", "database", "db", "schema", "model", "migration", "prisma", "drizzle", "sql", "redis", "store")
    if re.search(r"\b(cache|persistence strategy)\b", q):
        add("Persistence Strategy", "cache", "redis", "store")
    if re.search(r"\b(route|api|http|request|response|endpoint|middleware|webhook)\b", q):
        add("Network Edge", "route", "api", "http", "request", "response", "endpoint", "middleware")
    if re.search(r"\b(queue|worker|job|cron|schedule|background|async)\b", q):
        add("Background Processing", "queue", "worker", "job", "cron", "schedule", "background")
    if re.search(r"\b(log|logging|telemetry|metric|tracing|observability|sentry|otel)\b", q):
        add("System Telemetry", "log", "logger", "telemetry", "metric", "tracing", "observability")
    if re.search(r"\b(secret|encrypt|decrypt|hash|csrf|cors|key|token)\b", q):
        add("Security Ops", "secret", "encrypt", "decrypt", "hash", "csrf", "cors", "key", "token")
    if re.search(r"\b(render|component|ui|view|page|screen)\b", q):
        add("Core Rendering", "render", "component", "ui", "view", "page", "screen")
    if re.search(r"\b(config|configuration|environment|env|settings)\b", q):
        add("Global Interface", "config", "configuration", "environment", "env", "settings")
    if re.search(r"\b(trace|flow|from .* to |touch|impact|change)\b", q):
        return QuestionIntent(tuple(blocks), tuple(keywords), requires_trace=True)
    return QuestionIntent(tuple(blocks), tuple(keywords))


def _answer_from_ranked_evidence(artifact_dir: Path, question: str, intent: QuestionIntent) -> EvidenceBundle:
    graph = _load_graph(artifact_dir)
    semantic_rows = _semantic_rows_by_node(artifact_dir)
    if not semantic_rows:
        return EvidenceBundle(
            query_type="answer_with_evidence",
            claim="No semantic-artifact.json assignments were available, so the question cannot be answered from block evidence.",
            confidence=0.0,
            limitations=["semantic-artifact.json missing or empty"],
        )

    nodes_by_id = graph["nodes_by_id"]
    ranked: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for node_id, row in semantic_rows.items():
        node = nodes_by_id.get(node_id)
        if not node:
            continue
        score = _score_candidate(node, row, intent)
        if score > 0:
            ranked.append((score, node, row))
    ranked.sort(key=lambda item: (-item[0], _is_test_path(str(item[1].get("file_path") or "")), str(item[1].get("file_path") or "")))

    chosen = _balanced_top_nodes(ranked, intent.blocks, per_block=4)
    if not chosen and ranked:
        chosen = ranked[: min(4, len(ranked))]
    if not chosen:
        return EvidenceBundle(
            query_type="answer_with_evidence",
            claim=f"No graph evidence matched the requested architecture concept(s): {', '.join(intent.blocks)}.",
            confidence=0.0,
            limitations=["semantic blocks exist, but none matched the question intent"],
        )

    source_nodes = [_evidence_node(node) for _score, node, _row in chosen]
    observed_blocks = set(intent.blocks).intersection(_blocks_for_rows([row for _score, _node, row in chosen]))
    confidence = _bundle_confidence(chosen, intent)
    paths = _paths_between_chosen_nodes(graph, [node for _score, node, _row in chosen])
    missing_blocks = [block for block in intent.blocks if block not in observed_blocks]
    limitations = []
    if missing_blocks:
        limitations.append(f"No selected evidence node covered expected block(s): {', '.join(missing_blocks)}")
    if not paths and intent.requires_trace and len(chosen) > 1:
        limitations.append("No explicit structural path connected the selected evidence nodes; answer is grouped evidence, not a proven flow trace.")

    return EvidenceBundle(
        query_type="answer_with_evidence",
        claim=_claim_for_answer(question, observed_blocks, source_nodes),
        confidence=confidence,
        source_nodes=source_nodes,
        file_ranges=_file_ranges([node for _score, node, _row in chosen]),
        paths=paths,
        limitations=limitations,
    )


def _score_candidate(node: dict[str, Any], row: dict[str, Any], intent: QuestionIntent) -> float:
    blocks = _blocks_for_rows([row])
    matched_blocks = set(intent.blocks).intersection(blocks)
    if not matched_blocks:
        return 0.0
    confidence = float(row.get("confidence") or 0.0)
    text = " ".join(
        str(part or "")
        for part in [
            node.get("file_path"),
            node.get("name"),
            node.get("kind"),
            row.get("reasoning"),
            node.get("content"),
        ]
    ).lower()
    block_keywords = {
        keyword
        for block in matched_blocks
        for keyword in _BLOCK_KEYWORDS.get(block, ())
    }
    keyword_hits = sum(1 for keyword in block_keywords if keyword and keyword.lower() in text)
    score = 3.0 * len(matched_blocks) + confidence * 3.0 + min(keyword_hits, 5) * 0.9
    if node.get("kind") == "file_surface":
        score -= 0.25
    if _is_test_path(str(node.get("file_path") or "")):
        score -= 1.5
    if intent.keywords and keyword_hits == 0:
        score -= 2.0
    if confidence < 0.35 and keyword_hits == 0:
        score -= 2.5
    return score


def _blocks_for_rows(rows: list[dict[str, Any]]) -> set[str]:
    blocks: set[str] = set()
    for row in rows:
        if row.get("primary_block"):
            blocks.add(str(row["primary_block"]))
        for secondary in row.get("secondary_blocks", []):
            if isinstance(secondary, dict) and secondary.get("block"):
                blocks.add(str(secondary["block"]))
    return blocks


def _balanced_top_nodes(
    ranked: list[tuple[float, dict[str, Any], dict[str, Any]]],
    blocks: tuple[str, ...],
    *,
    per_block: int,
) -> list[tuple[float, dict[str, Any], dict[str, Any]]]:
    chosen: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    seen_ids: set[str] = set()
    seen_file_block: set[tuple[str, str]] = set()
    for block in blocks:
        picked_for_block = 0
        block_ranked = sorted(ranked, key=lambda item: (-_score_for_block(item[1], item[2], block), _is_test_path(str(item[1].get("file_path") or ""))))
        for item in block_ranked:
            _score, node, row = item
            node_id = str(node.get("node_id") or node.get("scip_id"))
            file_path = str(node.get("file_path") or "")
            if node_id in seen_ids:
                continue
            if (file_path, block) in seen_file_block:
                continue
            if block in _blocks_for_rows([row]):
                chosen.append(item)
                seen_ids.add(node_id)
                seen_file_block.add((file_path, block))
                picked_for_block += 1
                if picked_for_block >= per_block:
                    break
    return chosen


def _score_for_block(node: dict[str, Any], row: dict[str, Any], block: str) -> float:
    primary = str(row.get("primary_block") or "")
    secondary_confidence = 0.0
    for secondary in row.get("secondary_blocks", []):
        if isinstance(secondary, dict) and secondary.get("block") == block:
            secondary_confidence = max(secondary_confidence, float(secondary.get("confidence") or 0.0))
    block_fit = float(row.get("confidence") or 0.0) if primary == block else secondary_confidence
    text = " ".join(
        str(part or "")
        for part in [node.get("file_path"), node.get("name"), node.get("kind"), row.get("reasoning"), node.get("content")]
    ).lower()
    keyword_hits = sum(1 for keyword in _BLOCK_KEYWORDS.get(block, ()) if keyword in text)
    score = block_fit * 4.0 + min(keyword_hits, 5) * 1.2
    if _is_test_path(str(node.get("file_path") or "")):
        score -= 2.0
    return score


def _paths_between_chosen_nodes(graph: dict[str, Any], nodes: list[dict[str, Any]]) -> list[EvidencePath]:
    ids = [str(node.get("node_id") or node.get("scip_id")) for node in nodes]
    out: list[EvidencePath] = []
    for start, end in zip(ids, ids[1:], strict=False):
        path = _bfs_path(graph, start, end, max_depth=4, directed=True)
        if path:
            out.append(
                EvidencePath(
                    node_ids=path["node_ids"],
                    edge_types=path["edge_types"],
                    edge_provenance=path.get("edge_provenance", []),
                    edge_direction=path.get("edge_direction", []),
                )
            )
        if len(out) >= 4:
            break
    return out


def _bundle_confidence(chosen: list[tuple[float, dict[str, Any], dict[str, Any]]], intent: QuestionIntent) -> float:
    observed = _blocks_for_rows([row for _score, _node, row in chosen])
    coverage = len(set(intent.blocks).intersection(observed)) / max(len(intent.blocks), 1)
    avg_semantic = sum(float(row.get("confidence") or 0.0) for _score, _node, row in chosen[:8]) / max(min(len(chosen), 8), 1)
    return round(min(0.25 + coverage * 0.45 + avg_semantic * 0.3, 0.95), 3)


def _claim_for_answer(question: str, observed_blocks: set[str], source_nodes: list[EvidenceNode]) -> str:
    files = sorted({node.file_path for node in source_nodes if node.file_path})
    block_text = ", ".join(sorted(observed_blocks)) or "unclassified architecture evidence"
    file_text = ", ".join(files[:5])
    suffix = f" Evidence starts in {file_text}." if file_text else ""
    return f"Question: {question} Matched block evidence for {block_text}.{suffix}"


def _snippet(node: dict[str, Any]) -> str | None:
    content = str(node.get("content") or "").strip()
    if not content:
        return None
    snippet = re.sub(r"\s+", " ", content[:240]).strip()
    return snippet.encode("ascii", errors="backslashreplace").decode("ascii")


def _is_test_path(path: str) -> bool:
    return bool(re.search(r"(^|/)(tests?|__tests__)/|(_test|\.test|\.spec)\.", path, re.I))


def _codes_tool_subgraph_paths(
    graph: dict[str, Any],
    seed_order: list[str],
    *,
    max_depth: int,
    max_edges: int,
) -> list[EvidencePath]:
    """Directed walks from seeds; round-robin expands one frontier hop per seed turn."""
    edges_out: list[EvidencePath] = []
    seen_edge_sets: set[frozenset[tuple[str, str, str]]] = set()
    structural_edges = graph["structural"].get("edges", [])

    frontiers: dict[str, deque[tuple[list[str], list[str], list[str | None], list[Literal["out", "in"]], int]]] = {}
    for seed in seed_order:
        if seed in graph["nodes_by_id"]:
            frontiers[seed] = deque([([seed], [], [], [], 0)])

    active = [s for s in seed_order if s in frontiers]
    rr = 0

    while len(edges_out) < max_edges and active and any(frontiers[s] for s in active):
        seed = active[rr % len(active)]
        rr += 1
        q = frontiers[seed]
        if not q:
            continue
        path_nodes, etypes, provs, dirs, hops = q.popleft()
        if hops >= max_depth:
            continue
        nid = path_nodes[-1]
        for edge in structural_edges:
            if len(edges_out) >= max_edges:
                break
            s = str(edge.get("source_id"))
            t = str(edge.get("target_id"))
            et = str(edge.get("edge_type") or "EDGE")
            prov_raw = edge.get("provenance")
            prov_s = str(prov_raw) if prov_raw is not None else None
            if s == nid:
                other = t
                direction: Literal["out", "in"] = "out"
            elif t == nid:
                other = s
                direction = "in"
            else:
                continue
            if other in path_nodes:
                continue
            est_key = frozenset({(nid, other, et)})
            if est_key in seen_edge_sets:
                continue
            seen_edge_sets.add(est_key)
            new_path = [*path_nodes, other]
            new_et = [*etypes, et]
            new_pr = [*provs, prov_s]
            new_dr = [*dirs, direction]
            edges_out.append(
                EvidencePath(
                    node_ids=new_path,
                    edge_types=new_et,
                    edge_provenance=new_pr,
                    edge_direction=new_dr,
                )
            )
            q.append((new_path, new_et, new_pr, new_dr, hops + 1))

    return edges_out


def _normalized_lexical_score(query: str, haystack: str) -> float:
    """Scale _text_score to ~[0,1] for confidence and abstention."""
    raw = _text_score(query, haystack)
    if raw <= 0:
        return 0.0
    terms = _terms(query)
    denom = max(len(terms), 1) + NORMALIZED_LEXICAL_DENOM_BIAS
    return min(raw / denom, 1.0)


def _retrieval_query_terms(query: str) -> list[str]:
    terms = _terms(query)
    out: list[str] = []
    seen: set[str] = set()
    for t in terms:
        bucket = {t, *_RETRIEVAL_TERM_EXPANSION.get(t, ())}
        for u in bucket:
            if u not in seen:
                seen.add(u)
                out.append(u)
    return out


def _text_score(query: str, text: str) -> float:
    return _text_score_terms(_terms(query), query, text)


def _text_score_terms(expanded_terms: list[str], query_phrase: str, text: str) -> float:
    if not expanded_terms:
        return 0.0
    haystack = text.lower()
    score = sum(1.0 for term in expanded_terms if term in haystack)
    phrase = query_phrase.strip().lower()
    if phrase and phrase in haystack:
        score += 3.0
    return score


def _terms(text: str) -> list[str]:
    stop = {
        "a",
        "an",
        "and",
        "are",
        "by",
        "for",
        "from",
        "how",
        "in",
        "is",
        "of",
        "on",
        "or",
        "the",
        "to",
        "what",
        "where",
        "which",
        "with",
    }
    return [term for term in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower()) if term not in stop]


def _rank_nodes_by_text(
    graph: dict[str, Any],
    query: str,
    *,
    limit: int,
    artifact_dir: Path | None = None,
) -> list[dict[str, Any]]:
    semantic_rows = _semantic_rows_by_node(artifact_dir) if artifact_dir else {}
    ranked: list[tuple[float, dict[str, Any]]] = []
    qlow = query.lower()
    file_like = re.findall(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]+\.[a-zA-Z0-9]+", qlow)
    query_terms = _retrieval_query_terms(query)
    for node in graph["nodes_by_id"].values():
        fp = str(node.get("file_path") or "")
        base = Path(fp).name if fp else ""
        nid = str(node.get("node_id") or node.get("scip_id") or "")
        row = semantic_rows.get(nid)
        sem_txt = ""
        if row:
            sem_txt = " ".join(str(row.get(k) or "") for k in ("reasoning", "primary_block"))
        hay = " ".join(
            str(part or "")
            for part in [
                node.get("repo_name"),
                node.get("file_path"),
                node.get("name"),
                node.get("kind"),
                node.get("content"),
                sem_txt,
                base,
            ]
        )
        score = _text_score_terms(query_terms, query, hay)
        if fp and Path(fp).name.lower() in qlow:
            score += 8.0
        for token in file_like:
            if base and token == base.lower():
                score += 12.0
                break
        if score > 0:
            ranked.append((score, node))
    ranked.sort(key=lambda item: (-item[0], _is_test_path(str(item[1].get("file_path") or "")), str(item[1].get("file_path") or "")))
    return _dedupe_nodes([node for _score, node in ranked])[:limit]


def _dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in nodes:
        node_id = str(node.get("node_id") or node.get("scip_id"))
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        out.append(node)
    return out


def _workflow_action_rank(action: str) -> int:
    order = {
        "CONFIGURE": 0,
        "AUTHORIZE": 1,
        "CONNECT": 2,
        "CREATE": 3,
        "PRODUCE": 4,
        "PROCESS": 5,
        "PERSIST": 6,
        "OBSERVE": 7,
        "RENDER": 8,
        "REPRESENT": 9,
    }
    return order.get(action.upper(), 50)
