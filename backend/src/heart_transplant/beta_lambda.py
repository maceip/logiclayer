from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import base64
import hashlib
import json
import os
import time
from http import HTTPStatus
from typing import Any

from heart_transplant.beta_runtime import load_limits, normalize_public_github_repo, run_hosted_analysis


DEFAULT_ALLOWED_ORIGINS = "https://maceip.github.io"


@dataclass(frozen=True)
class RateDecision:
    allowed: bool
    retry_after_seconds: int = 0
    reason: str = "ok"


class SmartTokenBucket:
    """DynamoDB-backed token bucket with escalating cooldowns for over-budget clients."""

    def __init__(self) -> None:
        self.table_name = os.environ.get("LOGICLENS_RATE_LIMIT_TABLE", "")
        self.capacity = float(os.environ.get("LOGICLENS_RATE_LIMIT_CAPACITY", "18"))
        self.refill_per_second = float(os.environ.get("LOGICLENS_RATE_LIMIT_REFILL_PER_SECOND", "0.08"))
        self.item_ttl_seconds = int(os.environ.get("LOGICLENS_RATE_LIMIT_ITEM_TTL_SECONDS", "86400"))
        self._table = None

    @property
    def table(self) -> Any | None:
        if not self.table_name:
            return None
        if self._table is None:
            import boto3

            self._table = boto3.resource("dynamodb").Table(self.table_name)
        return self._table

    def allow(self, *, identity: str, cost: float) -> RateDecision:
        if self.table is None:
            return RateDecision(allowed=True)

        now = time.time()
        key = {"pk": identity}
        item = self.table.get_item(Key=key, ConsistentRead=True).get("Item", {})
        tokens = float(item.get("tokens", self.capacity))
        updated_at = float(item.get("updated_at", now))
        strikes = int(item.get("strikes", 0))
        blocked_until = float(item.get("blocked_until", 0))
        tokens = min(self.capacity, tokens + max(0, now - updated_at) * self.refill_per_second)

        if blocked_until > now:
            return RateDecision(False, retry_after_seconds=max(1, int(blocked_until - now)), reason="cooldown")

        if tokens < cost:
            strikes += 1
            cooldown = min(900, 2 ** min(strikes, 9))
            self._put(identity, tokens=tokens, now=now, strikes=strikes, blocked_until=now + cooldown)
            return RateDecision(False, retry_after_seconds=cooldown, reason="token_budget")

        tokens -= cost
        strikes = max(0, strikes - 1)
        self._put(identity, tokens=tokens, now=now, strikes=strikes, blocked_until=0)
        return RateDecision(True)

    def _put(self, identity: str, *, tokens: float, now: float, strikes: int, blocked_until: float) -> None:
        assert self.table is not None
        self.table.put_item(
            Item={
                "pk": identity,
                "tokens": str(round(tokens, 4)),
                "updated_at": str(round(now, 4)),
                "strikes": strikes,
                "blocked_until": str(round(blocked_until, 4)),
                "expires_at": int(now) + self.item_ttl_seconds,
            }
        )


RATE_LIMITER = SmartTokenBucket()


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    method = event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod", "GET")
    path = event.get("rawPath") or event.get("path") or "/"
    headers = _headers(event)
    origin = headers.get("origin", "")
    allowed_origin = _allowed_origin(origin)

    if method == "OPTIONS":
        if not allowed_origin:
            return _response(HTTPStatus.FORBIDDEN, {"error": "origin_not_allowed"}, origin="")
        return _response(HTTPStatus.NO_CONTENT, {}, origin=allowed_origin)

    if not allowed_origin:
        return _response(HTTPStatus.FORBIDDEN, {"error": "origin_not_allowed"}, origin="")

    try:
        if path.endswith("/api/health") or path == "/health":
            decision = RATE_LIMITER.allow(identity=_identity(headers, origin), cost=0.25)
            if not decision.allowed:
                return _rate_limited(decision, allowed_origin)
            return _response(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "mode": "lambda_sync",
                    "sync": True,
                    "active_jobs": 0,
                    "max_active_jobs": 1,
                    "rate_limit": "dynamodb_token_bucket",
                },
                origin=allowed_origin,
            )

        if method == "POST" and (path.endswith("/api/analyze") or path == "/analyze"):
            body = _json_body(event)
            repo = normalize_public_github_repo(str(body.get("repo") or ""))
            decision = RATE_LIMITER.allow(identity=_identity(headers, origin, repo=repo), cost=_analysis_cost(repo))
            if not decision.allowed:
                return _rate_limited(decision, allowed_origin)

            _configure_serverless_runtime()
            result = run_hosted_analysis(repo, limits=load_limits())
            return _response(
                HTTPStatus.OK,
                {
                    "job_id": f"lambda-{hashlib.sha256((repo + result['finished_at']).encode()).hexdigest()[:16]}",
                    "repo": repo,
                    "status": "succeeded",
                    "stage": "done",
                    "message": "Analysis complete.",
                    "created_at": result["started_at"],
                    "updated_at": result["finished_at"],
                    "result": result,
                },
                origin=allowed_origin,
            )

        return _response(HTTPStatus.NOT_FOUND, {"error": "not_found"}, origin=allowed_origin)
    except Exception as exc:  # noqa: BLE001 - public API returns concise job errors
        return _response(
            HTTPStatus.BAD_REQUEST,
            {
                "status": "failed",
                "stage": "failed",
                "message": str(exc),
                "error": str(exc),
                "updated_at": datetime.now(UTC).isoformat(),
            },
            origin=allowed_origin,
        )


def _configure_serverless_runtime() -> None:
    os.environ.setdefault("HEART_TRANSPLANT_BETA_FETCH_MODE", "zipball")
    os.environ.setdefault("HEART_TRANSPLANT_BETA_CACHE", "/tmp/logiclens/repos")
    os.environ.setdefault("HEART_TRANSPLANT_ARTIFACT_ROOT", "/tmp/logiclens/artifacts")
    os.environ.setdefault("HEART_TRANSPLANT_BETA_MAX_SOURCE_FILES", "12000")
    os.environ.setdefault("HEART_TRANSPLANT_BETA_MAX_FILE_BYTES", "384000")
    os.environ.setdefault("HEART_TRANSPLANT_BETA_MAX_RETURNED_SURFACES", "180")


def _headers(event: dict[str, Any]) -> dict[str, str]:
    return {str(k).lower(): str(v) for k, v in (event.get("headers") or {}).items() if v is not None}


def _allowed_origin(origin: str) -> str:
    allowed = {item.strip() for item in os.environ.get("LOGICLENS_ALLOWED_ORIGINS", DEFAULT_ALLOWED_ORIGINS).split(",") if item.strip()}
    return origin if origin in allowed else ""


def _identity(headers: dict[str, str], origin: str, *, repo: str = "") -> str:
    forwarded = headers.get("x-forwarded-for", "")
    client_ip = forwarded.split(",", 1)[0].strip() or headers.get("x-real-ip", "unknown")
    user_agent = headers.get("user-agent", "unknown")[:160]
    raw = "|".join([origin, client_ip, user_agent, repo])
    return "logiclens#" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _analysis_cost(repo: str) -> float:
    owner, name = repo.split("/", 1)
    # Slightly higher cost for large-looking namespace/repo names and repeatable public repos.
    return min(9.0, 5.0 + (len(owner) + len(name)) / 80)


def _json_body(event: dict[str, Any]) -> dict[str, Any]:
    raw = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    payload = json.loads(raw or "{}")
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    return payload


def _rate_limited(decision: RateDecision, origin: str) -> dict[str, Any]:
    return _response(
        HTTPStatus.TOO_MANY_REQUESTS,
        {"error": "rate_limited", "reason": decision.reason, "retry_after_seconds": decision.retry_after_seconds},
        origin=origin,
        extra_headers={"Retry-After": str(decision.retry_after_seconds)},
    )


def _response(status: int, payload: dict[str, Any], *, origin: str, extra_headers: dict[str, str] | None = None) -> dict[str, Any]:
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Cache-Control": "no-store",
        "Vary": "Origin",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Access-Control-Allow-Headers": "content-type",
        "Access-Control-Max-Age": "600",
    }
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
    if extra_headers:
        headers.update(extra_headers)
    return {
        "statusCode": int(status),
        "headers": headers,
        "body": "" if status == HTTPStatus.NO_CONTENT else json.dumps(payload, ensure_ascii=True),
    }
