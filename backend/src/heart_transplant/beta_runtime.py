from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from heart_transplant.artifact_manifest import write_artifact_manifest
from heart_transplant.artifact_store import persist_structural_artifact, read_json
from heart_transplant.classify.pipeline import run_classification_on_artifact
from heart_transplant.graph_integrity import run_graph_integrity
from heart_transplant.ingest.treesitter_ingest import ingest_repository

REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}$")


@dataclass(frozen=True)
class BetaLimits:
    max_source_files: int = 20_000
    max_file_bytes: int = 512_000
    clone_timeout_seconds: int = 240
    update_timeout_seconds: int = 90
    max_returned_surfaces: int = 240


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def normalize_public_github_repo(value: str) -> str:
    trimmed = value.strip().split("?", 1)[0].split("#", 1)[0].rstrip("/")
    ssh_match = re.fullmatch(r"git@github\.com:(?P<owner>[^/\s]+)/(?P<repo>[^/\s]+?)(?:\.git)?", trimmed, re.IGNORECASE)
    if ssh_match:
        trimmed = f"{ssh_match.group('owner')}/{ssh_match.group('repo').removesuffix('.git')}"
    elif "github.com" in trimmed.lower():
        parsed = urlparse(trimmed if "://" in trimmed else f"https://{trimmed}")
        if parsed.netloc.lower() != "github.com":
            raise ValueError("Repository must be a public GitHub owner/name or github.com URL.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) != 2:
            raise ValueError("Repository URL must point to a repository root, not a branch, file, or subpath.")
        name = parts[1].removesuffix(".git")
        trimmed = f"{parts[0]}/{name}"
    if not REPO_PATTERN.match(trimmed):
        raise ValueError("Repository must be a public GitHub owner/name or github.com URL.")
    owner, name = trimmed.split("/", 1)
    return f"{owner}/{name}"


def beta_cache_root() -> Path:
    configured = os.environ.get("HEART_TRANSPLANT_BETA_CACHE")
    return Path(configured).resolve() if configured else repo_root() / ".heart-transplant" / "beta" / "repos"


def load_limits() -> BetaLimits:
    return BetaLimits(
        max_source_files=int(os.environ.get("HEART_TRANSPLANT_BETA_MAX_SOURCE_FILES", "20000")),
        max_file_bytes=int(os.environ.get("HEART_TRANSPLANT_BETA_MAX_FILE_BYTES", "512000")),
        clone_timeout_seconds=int(os.environ.get("HEART_TRANSPLANT_BETA_CLONE_TIMEOUT", "240")),
        update_timeout_seconds=int(os.environ.get("HEART_TRANSPLANT_BETA_UPDATE_TIMEOUT", "90")),
        max_returned_surfaces=int(os.environ.get("HEART_TRANSPLANT_BETA_MAX_RETURNED_SURFACES", "240")),
    )


ProgressCallback = Callable[[str, str], None]


def run_hosted_analysis(repo: str, *, limits: BetaLimits | None = None, progress: ProgressCallback | None = None) -> dict[str, Any]:
    """Clone a public GitHub repository and run the beta-safe backend pipeline.

    This intentionally avoids package installs, OpenAI calls, and arbitrary local
    paths. It is safe enough for an unauthenticated beta endpoint while still
    exercising the real Tree-sitter ingest, artifact manifest, classifier, and
    graph integrity rails.
    """

    chosen_limits = limits or load_limits()
    normalized_repo = normalize_public_github_repo(repo)
    started = datetime.now(UTC)
    notify(progress, "clone", f"Cloning or updating {normalized_repo}.")
    repo_path, repo_warning = clone_or_reuse_public_repo(normalized_repo, chosen_limits)

    notify(progress, "ingest", f"Running Tree-sitter ingest with source and generated-file budgets.")
    artifact = ingest_repository(
        repo_path=repo_path,
        repo_name=normalized_repo,
        max_source_files=chosen_limits.max_source_files,
        max_file_bytes=chosen_limits.max_file_bytes,
        extra_ignored_dirs=beta_generated_dirs(),
    )
    notify(progress, "artifact", f"Persisting {artifact.node_count} nodes and {artifact.edge_count} edges.")
    artifact_dir = persist_structural_artifact(artifact)
    notify(progress, "classify", "Classifying architecture blocks with deterministic heuristics.")
    semantic = run_classification_on_artifact(artifact_dir, use_openai=False)
    notify(progress, "manifest", "Writing artifact manifest receipt.")
    manifest = write_artifact_manifest(artifact_dir, command="beta-api analyze")
    notify(progress, "integrity", "Running graph integrity checks.")
    graph_integrity = run_graph_integrity(artifact_dir)
    finished = datetime.now(UTC)

    block_counts = Counter(a.primary_block for a in semantic.block_assignments)
    semantic_by_node = {a.node_id: a for a in semantic.block_assignments}
    surfaces = []
    for node in artifact.code_nodes:
        assignment = semantic_by_node.get(node.scip_id)
        if assignment is None:
            continue
        surfaces.append(
            {
                "path": node.file_path,
                "name": node.name,
                "kind": str(node.kind.value if hasattr(node.kind, "value") else node.kind),
                "language": node.language,
                "block": assignment.primary_block,
                "confidence": assignment.confidence,
                "signal": assignment.reasoning,
            }
        )
    surfaces.sort(key=lambda item: (-float(item["confidence"]), str(item["path"])))
    insights = build_operator_insights(surfaces, block_counts)

    return {
        "repo": normalized_repo,
        "repo_path": str(repo_path),
        "artifact_dir": str(artifact_dir),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "summary": {
            "node_count": artifact.node_count,
            "edge_count": artifact.edge_count,
            "file_count": len(artifact.file_nodes),
            "parser_backends": artifact.parser_backends,
            "block_counts": dict(sorted(block_counts.items(), key=lambda item: (-item[1], item[0]))),
            "graph_integrity": graph_integrity.get("summary", {}),
            "manifest": manifest.get("summary", {}),
        },
        "insights": insights,
        "runtime_capabilities": {
            "repo_source": "public_github_clone_depth_1",
            "structural_ingest": "python_tree_sitter_language_pack",
            "semantic_index": "not_enabled_for_unauthenticated_beta",
            "classifier": "deterministic_heuristic_no_openai",
            "graph_store": "artifact_json_surreal_ready",
            "artifact_manifest": "artifact-manifest.json",
            "graph_integrity": "layer_specific_checks",
            "browser_runtime_plan": "tree_sitter_wasm_and_surrealdb_wasm_adapter",
        },
        "warnings": [repo_warning] if repo_warning else [],
        "surfaces": surfaces[: chosen_limits.max_returned_surfaces],
    }


def notify(progress: ProgressCallback | None, stage: str, message: str) -> None:
    if progress:
        progress(stage, message)


def beta_generated_dirs() -> set[str]:
    return {
        ".claude",
        ".github",
        "coverage",
        "docs_site",
        "friscy-bundle",
        "golden_demo",
        "public",
        "vendor",
    }


def build_operator_insights(surfaces: list[dict[str, Any]], block_counts: Counter[str]) -> list[dict[str, Any]]:
    by_block: dict[str, list[dict[str, Any]]] = {}
    for surface in surfaces:
        by_block.setdefault(str(surface["block"]), []).append(surface)

    def samples(blocks: list[str], limit: int = 5) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for block in blocks:
            rows.extend(by_block.get(block, [])[:limit])
        deduped: dict[str, dict[str, Any]] = {}
        for row in rows:
            deduped.setdefault(f"{row['path']}::{row['name']}::{row['block']}", row)
        return list(deduped.values())[:limit]

    auth = samples(["Access Control", "Security Ops"])
    impact = samples(["Network Edge", "Connectivity Layer", "Data Persistence", "Background Processing"])
    risk = samples(["Access Control", "Security Ops", "System Telemetry", "Error Boundaries", "Resiliency"])
    low_confidence = sorted([s for s in surfaces if float(s.get("confidence", 0)) < 0.62], key=lambda item: float(item["confidence"]))[:6]
    dominant = [
        {"block": block, "count": count}
        for block, count in sorted(block_counts.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]

    insights = [
        {
            "title": "Where is auth?",
            "answer": "These are the best access-control and security candidates from the current run. Treat them as the first places to inspect, not as a final security audit.",
            "samples": auth,
            "empty_state": "No strong auth or security surfaces found in this run.",
        },
        {
            "title": "What changes if I touch this?",
            "answer": "The first impact model is boundary-based: files near network edges, service adapters, persistence, and queues are likelier to affect multiple behaviors.",
            "samples": impact,
            "empty_state": "No strong change-impact surfaces found in this run.",
        },
        {
            "title": "What are the risky seams?",
            "answer": "These are operationally sensitive paths: auth, security, telemetry, error handling, and resiliency surfaces that deserve extra review before edits.",
            "samples": risk,
            "empty_state": "No strong operational risk surfaces found in this run.",
        },
        {
            "title": "What should I refactor first?",
            "answer": "Today this points at low-confidence or weakly explained surfaces. Long term this becomes regret scoring plus blast-radius simulation.",
            "samples": low_confidence,
            "empty_state": "No low-confidence rows returned in the bounded result window.",
        },
        {
            "title": "Show me evidence.",
            "answer": "Every answer above is backed by concrete file/node rows. The block distribution stays here as the supporting chart, not the pitch.",
            "samples": [],
            "dominant_blocks": dominant,
            "empty_state": "No block distribution available.",
        },
    ]
    return insights


def clone_or_reuse_public_repo(repo: str, limits: BetaLimits) -> tuple[Path, str | None]:
    if os.environ.get("HEART_TRANSPLANT_BETA_FETCH_MODE") == "zipball":
        return fetch_public_repo_zipball(repo, limits)

    owner, name = repo.split("/", 1)
    cache_root = beta_cache_root()
    cache_root.mkdir(parents=True, exist_ok=True)
    target = cache_root / f"{owner}__{name}"
    git = shutil.which("git")
    if not git:
        raise RuntimeError("git is required for hosted beta analysis.")

    if not target.exists():
        url = f"https://github.com/{repo}.git"
        subprocess.run(
            [git, "clone", "--depth", "1", "--no-tags", url, str(target)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=limits.clone_timeout_seconds,
        )
        return target, None

    if not (target / ".git").is_dir():
        raise RuntimeError(f"Cached beta repo path is not a git checkout: {target}")

    try:
        subprocess.run(
            [git, "-C", str(target), "pull", "--ff-only", "--no-tags"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=limits.update_timeout_seconds,
        )
        return target, None
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return target, f"Using cached checkout because update failed: {type(exc).__name__}"


def fetch_public_repo_zipball(repo: str, limits: BetaLimits) -> tuple[Path, str | None]:
    """Fetch a public GitHub repo as a zipball for serverless runtimes without git."""

    owner, name = repo.split("/", 1)
    cache_root = beta_cache_root()
    cache_root.mkdir(parents=True, exist_ok=True)
    target = cache_root / f"{owner}__{name}"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    url = f"https://api.github.com/repos/{repo}/zipball/HEAD"
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "logiclens-beta-lambda"})
    with urlopen(request, timeout=limits.clone_timeout_seconds) as response:  # noqa: S310 - fixed GitHub API host
        archive = response.read()
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        safe_members = [member for member in zf.infolist() if not _zip_member_is_unsafe(member.filename)]
        zf.extractall(target, safe_members)

    roots = [path for path in target.iterdir() if path.is_dir()]
    if len(roots) == 1:
        return roots[0], "Fetched GitHub zipball; git history is not available in serverless mode."
    return target, "Fetched GitHub zipball; archive root could not be collapsed."


def _zip_member_is_unsafe(name: str) -> bool:
    path = Path(name)
    return path.is_absolute() or ".." in path.parts


def write_json_response(handler: Any, status: int, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)
