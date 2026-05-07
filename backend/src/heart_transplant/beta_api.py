from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
import time
from typing import Any
from urllib.parse import unquote, urlparse

from heart_transplant.beta_runtime import load_limits, repo_root, run_hosted_analysis, write_json_response
from heart_transplant.beta_lambda import _requested_repos, run_multi_repo_analysis


@dataclass
class Job:
    job_id: str
    repo: str
    repos: list[str] = field(default_factory=list)
    status: str = "queued"
    stage: str = "queued"
    message: str = "Waiting for analyzer capacity."
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    result: dict[str, Any] | None = None
    error: str | None = None


class JobStore:
    def __init__(self, *, max_active: int, max_jobs: int) -> None:
        self.max_active = max_active
        self.max_jobs = max_jobs
        self.jobs: dict[str, Job] = {}
        self.active = 0
        self.lock = threading.Lock()

    def submit(self, repos: list[str]) -> Job:
        with self.lock:
            self._trim_locked()
            if self.active >= self.max_active:
                raise RuntimeError("Analyzer is busy. Please retry shortly.")
            if len(self.jobs) >= self.max_jobs:
                raise RuntimeError("Job buffer is full. Please retry shortly.")
            job = Job(job_id=secrets.token_urlsafe(12), repo=" + ".join(repos), repos=repos)
            self.jobs[job.job_id] = job
            self.active += 1
        thread = threading.Thread(target=self._run, args=(job.job_id,), daemon=True)
        thread.start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self.lock:
            return self.jobs.get(job_id)

    def _run(self, job_id: str) -> None:
        self._mark(job_id, status="running", stage="starting", message="Starting hosted analysis.")
        try:
            with self.lock:
                repos = self.jobs[job_id].repos or [self.jobs[job_id].repo]

            def progress(stage: str, message: str) -> None:
                self._mark(job_id, status="running", stage=stage, message=message)

            result = run_multi_repo_analysis(repos) if len(repos) > 1 else run_hosted_analysis(repos[0], limits=load_limits(), progress=progress)
            self._mark(job_id, status="succeeded", stage="done", message="Analysis complete.", result=result)
        except Exception as exc:  # noqa: BLE001 - user-facing job error
            self._mark(job_id, status="failed", stage="failed", message=str(exc), error=str(exc))
        finally:
            with self.lock:
                self.active = max(0, self.active - 1)

    def _mark(
        self,
        job_id: str,
        *,
        status: str,
        stage: str | None = None,
        message: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with self.lock:
            job = self.jobs[job_id]
            job.status = status
            if stage:
                job.stage = stage
            if message:
                job.message = message
            job.updated_at = datetime.now(UTC).isoformat()
            job.result = result
            job.error = error

    def _trim_locked(self) -> None:
        if len(self.jobs) < self.max_jobs:
            return
        finished = [job for job in self.jobs.values() if job.status in {"succeeded", "failed"}]
        finished.sort(key=lambda job: job.updated_at)
        for job in finished[: max(1, len(finished) // 3)]:
            self.jobs.pop(job.job_id, None)


class RateLimiter:
    def __init__(self, *, per_minute: int) -> None:
        self.per_minute = per_minute
        self.hits: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self.lock:
            hits = [t for t in self.hits.get(key, []) if now - t < 60]
            if len(hits) >= self.per_minute:
                self.hits[key] = hits
                return False
            hits.append(now)
            self.hits[key] = hits
            return True


def make_handler(docs_dir: Path, job_store: JobStore, limiter: RateLimiter) -> type[SimpleHTTPRequestHandler]:
    class BetaHandler(SimpleHTTPRequestHandler):
        server_version = "HeartTransplantBeta/0.1"

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(docs_dir), **kwargs)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/api/health":
                write_json_response(
                    self,
                    HTTPStatus.OK,
                    {
                        "ok": True,
                        "mode": "hosted_beta",
                        "max_active_jobs": job_store.max_active,
                        "active_jobs": job_store.active,
                    },
                )
                return
            if path.startswith("/api/jobs/"):
                job_id = unquote(path.rsplit("/", 1)[-1])
                job = job_store.get(job_id)
                if not job:
                    write_json_response(self, HTTPStatus.NOT_FOUND, {"error": "job_not_found"})
                    return
                write_json_response(self, HTTPStatus.OK, job_to_json(job))
                return
            return super().do_GET()

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path != "/api/analyze":
                write_json_response(self, HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return
            client = self.client_address[0] if self.client_address else "unknown"
            if not limiter.allow(client):
                write_json_response(self, HTTPStatus.TOO_MANY_REQUESTS, {"error": "rate_limited"})
                return
            try:
                payload = self._read_json_body()
                repos = _requested_repos(payload)
                job = job_store.submit(repos)
            except Exception as exc:  # noqa: BLE001 - request error payload
                write_json_response(self, HTTPStatus.BAD_REQUEST, {"error": str(exc)})
                return
            write_json_response(self, HTTPStatus.ACCEPTED, job_to_json(job))

        def _read_json_body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0 or length > 16_384:
                raise ValueError("Request body must be JSON and smaller than 16KB.")
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object.")
            return payload

        def log_message(self, format: str, *args: Any) -> None:
            if os.environ.get("HEART_TRANSPLANT_BETA_QUIET") == "1":
                return
            super().log_message(format, *args)

    return BetaHandler


def job_to_json(job: Job) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "repo": job.repo,
        "repos": job.repos,
        "status": job.status,
        "stage": job.stage,
        "message": job.message,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "result": job.result,
        "error": job.error,
    }


def serve_beta(host: str = "127.0.0.1", port: int = 8089, docs_dir: Path | None = None) -> None:
    root = repo_root()
    chosen_docs = (docs_dir or (root / "docs")).resolve()
    max_active = int(os.environ.get("HEART_TRANSPLANT_BETA_MAX_ACTIVE", "1"))
    max_jobs = int(os.environ.get("HEART_TRANSPLANT_BETA_MAX_JOBS", "24"))
    per_minute = int(os.environ.get("HEART_TRANSPLANT_BETA_RATE_PER_MINUTE", "6"))
    handler = make_handler(chosen_docs, JobStore(max_active=max_active, max_jobs=max_jobs), RateLimiter(per_minute=per_minute))
    server = ThreadingHTTPServer((host, port), handler)
    print(f"heart-transplant beta serving http://{host}:{port}/ from {chosen_docs}")
    server.serve_forever()
