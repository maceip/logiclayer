from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from heart_transplant.artifact_store import read_json
from heart_transplant.evidence import EvidenceBundle, answer_with_evidence


def load_evidence_questions(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    if not isinstance(data, list):
        raise ValueError(f"Evidence questions must be a JSON list: {path}")
    return [row for row in data if isinstance(row, dict)]


def run_evidence_benchmark(
    artifact_dir: Path,
    questions: list[dict[str, Any]],
    *,
    question_set_path: Path | None = None,
    fail_on_hallucinations: bool = False,
) -> dict[str, Any]:
    structural = read_json(Path(artifact_dir) / "structural-artifact.json")
    repo_name = str(structural.get("repo_name", ""))
    active_questions = [normalize_question(row) for row in questions if str(row.get("status", "active")) == "active"]
    scoped_questions = [row for row in active_questions if question_applies_to_artifact(row, repo_name)]
    semantic_blocks = _semantic_blocks_by_node(artifact_dir)

    rows = []
    correct = 0
    unsupported_questions = 0
    unsupported_correct = 0
    hallucinations = 0
    missing_evidence = 0
    for question in scoped_questions:
        bundle = answer_with_evidence(artifact_dir, question["question"])
        result = score_evidence_answer(question, bundle, semantic_blocks)
        if result["match"]:
            correct += 1
        if result["unsupported_expected"]:
            unsupported_questions += 1
            if result["unsupported_correct"]:
                unsupported_correct += 1
            if result["hallucinated"]:
                hallucinations += 1
        if not result["has_evidence"] and not result["unsupported_expected"]:
            missing_evidence += 1
        rows.append({**question, **result, "answer": bundle.model_dump(mode="json")})

    return {
        "report_type": "evidence_benchmark",
        "artifact_dir": str(Path(artifact_dir).resolve()),
        "question_set": str(question_set_path) if question_set_path else None,
        "summary": {
            "input_questions": len(questions),
            "active_questions": len(active_questions),
            "scored_questions": len(scoped_questions),
            "correct": correct,
            "accuracy": correct / max(len(scoped_questions), 1),
            "skipped_repo_scope": len(active_questions) - len(scoped_questions),
            "unsupported_questions": unsupported_questions,
            "unsupported_correct": unsupported_correct,
            "unsupported_correct_rate": unsupported_correct / max(unsupported_questions, 1),
            "hallucination_count": hallucinations,
            "hallucination_rate": hallucinations / max(unsupported_questions, 1),
            "missing_evidence_count": missing_evidence,
            "fail_on_hallucinations": fail_on_hallucinations,
        },
        "rows": rows,
    }


def normalize_question(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "repo_name": str(row.get("repo_name") or ""),
        "question": str(row.get("question") or ""),
        "expected_blocks": [str(item) for item in row.get("expected_blocks", []) if str(item or "").strip()],
        "expected_files": [str(item) for item in row.get("expected_files", []) if str(item or "").strip()],
        "expected_file_globs": [str(item) for item in row.get("expected_file_globs", []) if str(item or "").strip()],
        "expected_query_types": [str(item) for item in row.get("expected_query_types", []) if str(item or "").strip()],
        "unsupported": bool(row.get("unsupported", False)),
        "source": str(row.get("source") or ""),
        "notes": str(row.get("notes") or ""),
        "status": str(row.get("status") or "active"),
        "partial_query_types": bool(row.get("partial_query_types", False)),
    }


def question_applies_to_artifact(question: dict[str, Any], artifact_repo_name: str) -> bool:
    repo_name = str(question.get("repo_name", "")).strip()
    if not repo_name:
        return True
    artifact_short = artifact_repo_name.rsplit("/", 1)[-1]
    return repo_name in {artifact_repo_name, artifact_short} or artifact_repo_name.endswith(f"/{repo_name}")


def score_evidence_answer(question: dict[str, Any], bundle: EvidenceBundle, semantic_blocks: dict[str, set[str]]) -> dict[str, Any]:
    source_files = sorted({node.file_path for node in bundle.source_nodes if node.file_path})
    source_node_ids = [node.node_id for node in bundle.source_nodes]
    observed_blocks = sorted({block for node_id in source_node_ids for block in semantic_blocks.get(node_id, set())})
    unsupported_expected = bool(question.get("unsupported"))
    unsupported_returned = bundle.confidence == 0.0 and not bundle.source_nodes
    hallucinated = unsupported_expected and bool(bundle.source_nodes)
    if unsupported_expected:
        return {
            "match": unsupported_returned,
            "has_evidence": bool(bundle.source_nodes),
            "block_match": not bundle.source_nodes,
            "file_match": not bundle.source_nodes,
            "unsupported_match": unsupported_returned,
            "unsupported_expected": True,
            "unsupported_returned": unsupported_returned,
            "unsupported_correct": unsupported_returned,
            "hallucinated": hallucinated,
            "observed_blocks": observed_blocks,
            "source_files": source_files,
        }
    expected_blocks = set(question["expected_blocks"])
    expected_files = set(question["expected_files"])
    expected_globs = question["expected_file_globs"]
    expected_qt = question.get("expected_query_types") or []
    block_match = not expected_blocks or bool(expected_blocks.intersection(observed_blocks))
    file_match = not expected_files and not expected_globs
    if expected_files:
        file_match = bool(expected_files.intersection(source_files))
    if expected_globs:
        file_match = file_match or any(fnmatch(path, pattern) for path in source_files for pattern in expected_globs)
    query_type_match = not expected_qt or _query_type_matches(
        bundle.query_type,
        expected_qt,
        bool(question.get("partial_query_types", False)),
    )
    has_evidence = bool(bundle.source_nodes)
    return {
        "match": bool(has_evidence and block_match and file_match and query_type_match),
        "has_evidence": has_evidence,
        "block_match": block_match,
        "file_match": file_match,
        "unsupported_match": None,
        "unsupported_expected": False,
        "unsupported_returned": False,
        "unsupported_correct": False,
        "hallucinated": False,
        "observed_blocks": observed_blocks,
        "source_files": source_files,
        "query_type_match": query_type_match,
    }


def _query_type_matches(observed: str, expected: list[str], partial: bool) -> bool:
    if observed in set(expected):
        return True
    if partial and observed == "query_projects_with_codes":
        return bool(set(expected).intersection({"query_codes", "query_projects"}))
    return False


def _semantic_blocks_by_node(artifact_dir: Path) -> dict[str, set[str]]:
    path = Path(artifact_dir) / "semantic-artifact.json"
    if not path.is_file():
        return {}
    semantic = read_json(path)
    out: dict[str, set[str]] = {}
    for row in semantic.get("block_assignments", []):
        node_id = str(row.get("node_id") or "")
        if not node_id:
            continue
        blocks = out.setdefault(node_id, set())
        if row.get("primary_block"):
            blocks.add(str(row["primary_block"]))
        for secondary in row.get("secondary_blocks", []):
            if isinstance(secondary, dict) and secondary.get("block"):
                blocks.add(str(secondary["block"]))
    return out
