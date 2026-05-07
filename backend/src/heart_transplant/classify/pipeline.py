from __future__ import annotations

from pathlib import Path

import os

from heart_transplant.artifact_store import read_json, write_json
from heart_transplant.classify.heuristic import classify_node_heuristic
from heart_transplant.models import CodeNode, NeighborhoodRecord, StructuralArtifact
from heart_transplant.semantic.enrichment import (
    build_semantic_actions,
    build_semantic_entities,
    build_semantic_summaries,
    build_system_summary,
    build_project_summary,
)
from heart_transplant.semantic.models import BlockAssignment, SemanticArtifact


def run_classification_on_artifact(
    artifact_dir: Path,
    *,
    use_openai: bool = True,
) -> SemanticArtifact:
    structural = read_json(artifact_dir / "structural-artifact.json")
    nbrs = structural.get("neighborhoods", {})
    a = StructuralArtifact.model_validate(structural)
    items: list[tuple[CodeNode, NeighborhoodRecord | None]] = []
    for c in a.code_nodes:
        raw = nbrs.get(c.scip_id) or nbrs.get(str(c.scip_id))
        nb = NeighborhoodRecord.model_validate(raw) if raw else None
        items.append((c, nb))
    if use_openai and os.environ.get("OPENAI_API_KEY"):
        from heart_transplant.classify.openai_blocks import classify_batch

        assignments = classify_batch(items, use_openai=True)
    else:
        assignments = [classify_node_heuristic(c, nb) for c, nb in items]
    enriched_items = [(node, neighbor, assignment) for (node, neighbor), assignment in zip(items, assignments, strict=True)]
    entities = build_semantic_entities(enriched_items)
    summaries = build_semantic_summaries(enriched_items)
    summaries.append(build_project_summary(a.project_node, summaries))
    summaries.append(build_system_summary(a.repo_name, [summaries[-1]]))
    sem = SemanticArtifact(
        artifact_id=str(structural.get("artifact_id", "unknown")),
        semantic_summaries=summaries,
        entities=entities,
        actions=build_semantic_actions(enriched_items, entities),
        block_assignments=assignments,
    )
    p = Path(artifact_dir) / "semantic-artifact.json"
    write_json(p, sem.model_dump(mode="json"))
    return sem


def persist_semantic_to_surreal(artifact_dir: Path) -> int:
    from heart_transplant.db.surreal_loader import load_block_assignments

    ap = Path(artifact_dir) / "semantic-artifact.json"
    if not ap.is_file():
        return 0
    data = read_json(ap)
    blocks = [BlockAssignment.model_validate(b) for b in data.get("block_assignments", [])]
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    return load_block_assignments(blocks, repo=str(structural.get("repo_name", "")), clear_repo=False)
