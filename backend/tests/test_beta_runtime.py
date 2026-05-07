from __future__ import annotations

from pathlib import Path

import pytest

from heart_transplant.beta_runtime import BetaLimits, normalize_public_github_repo, run_hosted_analysis


def test_normalize_public_github_repo_accepts_owner_name_and_url() -> None:
    assert normalize_public_github_repo("openai/codex") == "openai/codex"
    assert normalize_public_github_repo("https://github.com/openai/codex.git") == "openai/codex"
    assert normalize_public_github_repo("https://github.com/openai/codex/") == "openai/codex"
    assert normalize_public_github_repo("git@github.com:openai/codex.git") == "openai/codex"


@pytest.mark.parametrize("value", ["", "openai", "../x/y", "https://example.com/a/b", "openai/codex/tree/main"])
def test_normalize_public_github_repo_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_public_github_repo(value)


def test_run_hosted_analysis_emits_runtime_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "server.ts").write_text(
        "export function routeUser() { return fetch('/api/user'); }\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("heart_transplant.beta_runtime.clone_or_reuse_public_repo", lambda repo, limits: (repo_dir, None))
    report = run_hosted_analysis("example/repo", limits=BetaLimits(max_source_files=20))

    assert report["repo"] == "example/repo"
    assert report["summary"]["node_count"] > 0
    assert report["summary"]["manifest"]["required_artifacts_present"] is True
    assert report["runtime_capabilities"]["classifier"] == "deterministic_heuristic_no_openai"
    assert report["insights"]
    assert report["surfaces"]


def test_run_hosted_analysis_uses_beta_ingest_budget(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / "src").mkdir()
    (repo_dir / "src" / "keep.ts").write_text("export function keep() { return true; }\n", encoding="utf-8")
    (repo_dir / "vendor").mkdir()
    (repo_dir / "vendor" / "skip.ts").write_text("export function skip() { return false; }\n", encoding="utf-8")
    (repo_dir / "huge.ts").write_text("export const value = `" + ("x" * 2000) + "`;\n", encoding="utf-8")

    monkeypatch.setattr("heart_transplant.beta_runtime.clone_or_reuse_public_repo", lambda repo, limits: (repo_dir, None))
    report = run_hosted_analysis("example/repo", limits=BetaLimits(max_source_files=20, max_file_bytes=1000))

    paths = {surface["path"] for surface in report["surfaces"]}
    assert "src/keep.ts" in paths
    assert "vendor/skip.ts" not in paths
    assert "huge.ts" not in paths
