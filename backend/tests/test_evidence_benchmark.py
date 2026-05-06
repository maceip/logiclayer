from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from heart_transplant.artifact_store import write_json
from heart_transplant.classify.pipeline import run_classification_on_artifact
from heart_transplant.cli import app
from heart_transplant.evals.evidence_benchmark import load_evidence_questions, run_evidence_benchmark
from heart_transplant.evidence import answer_with_evidence
from heart_transplant.ingest.treesitter_ingest import ingest_repository


def test_evidence_benchmark_scores_expected_blocks_and_files(tmp_path: Path) -> None:
    artifact_dir = _artifact_with_semantics(tmp_path)
    questions = [
        {
            "id": "fixture-auth",
            "repo_name": "test/evidence",
            "question": "Where is auth handled?",
            "expected_blocks": ["Access Control"],
            "expected_files": ["auth.ts"],
            "expected_file_globs": [],
            "source": "test",
            "notes": "",
            "status": "active",
        }
    ]

    report = run_evidence_benchmark(artifact_dir, questions)

    assert report["summary"]["scored_questions"] == 1
    assert report["summary"]["accuracy"] == 1.0
    assert report["rows"][0]["block_match"] is True
    assert report["rows"][0]["file_match"] is True
    assert report["summary"]["hallucination_rate"] == 0.0


def test_evidence_benchmark_scores_unsupported_questions(tmp_path: Path) -> None:
    artifact_dir = _artifact_with_semantics(tmp_path)
    questions = [
        {
            "id": "fixture-kafka",
            "repo_name": "test/evidence",
            "question": "Where is Kafka configured?",
            "expected_blocks": [],
            "expected_files": [],
            "expected_file_globs": [],
            "unsupported": True,
            "source": "test",
            "notes": "",
            "status": "active",
        }
    ]

    report = run_evidence_benchmark(artifact_dir, questions)

    assert report["summary"]["unsupported_correct_rate"] == 1.0
    assert report["summary"]["hallucination_rate"] == 0.0
    assert report["rows"][0]["unsupported_correct"] is True


def test_evidence_benchmark_cli_runs_question_file(tmp_path: Path) -> None:
    artifact_dir = _artifact_with_semantics(tmp_path)
    questions = tmp_path / "questions.json"
    write_json(
        questions,
        [
            {
                "id": "fixture-auth",
                "repo_name": "test/evidence",
                "question": "Where is auth handled?",
                "expected_blocks": ["Access Control"],
                "expected_files": ["auth.ts"],
                "expected_file_globs": [],
                "source": "test",
                "notes": "",
                "status": "active",
            }
        ],
    )
    runner = CliRunner()

    result = runner.invoke(app, ["evidence-benchmark", str(artifact_dir), "--questions", str(questions)])

    assert result.exit_code == 0
    assert json.loads(result.output)["summary"]["correct"] == 1
    assert load_evidence_questions(questions)[0]["id"] == "fixture-auth"


def test_answer_with_evidence_handles_multi_block_paper_question(tmp_path: Path) -> None:
    artifact_dir = _artifact_with_semantics(tmp_path)

    bundle = answer_with_evidence(
        artifact_dir,
        "Trace how a user session is established from HTTP entry to persistence.",
    )

    files = {node.file_path for node in bundle.source_nodes}
    assert bundle.query_type == "answer_with_evidence"
    assert bundle.confidence > 0.5
    assert "auth.ts" in files
    assert "db.ts" in files
    assert "route.ts" in files


def test_evidence_benchmark_meets_phase17_thresholds() -> None:
    """Phase 17: committed logiclens fixture must keep accuracy >= 0.80 and zero hallucinations."""
    repo_root = Path(__file__).resolve().parents[2]
    artifact_dir = repo_root / "docs" / "evals" / "fixtures" / "logiclens-evidence-benchmark"
    questions_path = repo_root / "docs" / "evals" / "evidence_questions.json"
    report_path = repo_root / "docs" / "evals" / "evidence_benchmark_report.json"

    assert artifact_dir.is_dir()
    assert questions_path.is_file()
    assert report_path.is_file()

    questions = load_evidence_questions(questions_path)
    report = run_evidence_benchmark(
        artifact_dir,
        questions,
        question_set_path=questions_path,
        fail_on_hallucinations=True,
    )
    summary = report["summary"]
    assert summary["scored_questions"] == 28
    assert summary["accuracy"] >= 0.8
    assert summary["hallucination_rate"] == 0.0

    committed = json.loads(report_path.read_text(encoding="utf-8"))
    assert committed["summary"]["accuracy"] >= 0.8
    assert committed["summary"]["hallucination_rate"] == 0.0


def test_evidence_benchmark_scores_unsupported_questions_as_abstentions(tmp_path: Path) -> None:
    artifact_dir = _artifact_with_semantics(tmp_path)
    questions = [
        {
            "id": "fixture-unsupported",
            "repo_name": "test/evidence",
            "question": "Where is the quantum scheduler configured?",
            "expected_blocks": [],
            "expected_files": [],
            "expected_file_globs": [],
            "unsupported": True,
            "source": "test",
            "notes": "",
            "status": "active",
        }
    ]

    report = run_evidence_benchmark(artifact_dir, questions)

    assert report["summary"]["accuracy"] == 1.0
    assert report["rows"][0]["unsupported_match"] is True


def _artifact_with_semantics(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "auth.ts").write_text("export function sessionGuard() { return true; }\n", encoding="utf-8")
    (repo / "route.ts").write_text("export function apiRoute(request: Request) { return sessionGuard(); }\n", encoding="utf-8")
    (repo / "db.ts").write_text("export const db = { query(sql: string) { return sql; } };\n", encoding="utf-8")
    artifact = ingest_repository(repo, "test/evidence")
    artifact_dir = tmp_path / "artifact"
    artifact_dir.mkdir()
    write_json(artifact_dir / "structural-artifact.json", artifact.model_dump(mode="json"))
    run_classification_on_artifact(artifact_dir, use_openai=False)
    return artifact_dir
