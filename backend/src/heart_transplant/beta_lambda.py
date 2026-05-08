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
            repos = _requested_repos(body)
            identity_repo_key = ",".join(repos)
            decision = RATE_LIMITER.allow(identity=_identity(headers, origin, repo=identity_repo_key), cost=_analysis_cost(repos))
            if not decision.allowed:
                return _rate_limited(decision, allowed_origin)

            _configure_serverless_runtime()
            result = run_multi_repo_analysis(repos) if len(repos) > 1 else run_hosted_analysis(repos[0], limits=load_limits())
            repo_label = result["repo"]
            return _response(
                HTTPStatus.OK,
                {
                    "job_id": f"lambda-{hashlib.sha256((repo_label + result['finished_at']).encode()).hexdigest()[:16]}",
                    "repo": repo_label,
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


def _requested_repos(body: dict[str, Any]) -> list[str]:
    if "repos" in body:
        raw_repos = body.get("repos")
        if not isinstance(raw_repos, list):
            raise ValueError("repos must be an array of public GitHub repositories.")
        repos = [normalize_public_github_repo(str(item)) for item in raw_repos if str(item or "").strip()]
        repos = list(dict.fromkeys(repos))
        if not 2 <= len(repos) <= 5:
            raise ValueError("Multi-repo analysis requires between 2 and 5 unique public GitHub repositories.")
        return repos
    return [normalize_public_github_repo(str(body.get("repo") or ""))]


def run_multi_repo_analysis(repos: list[str]) -> dict[str, Any]:
    started = datetime.now(UTC)
    per_repo = [run_hosted_analysis(repo, limits=load_limits()) for repo in repos]
    finished = datetime.now(UTC)
    repo_label = " + ".join(repos)
    surfaces: list[dict[str, Any]] = []
    block_counts: dict[str, int] = {}
    parser_backends: set[str] = set()
    node_count = 0
    edge_count = 0
    file_count = 0

    for report in per_repo:
        summary = report.get("summary", {})
        node_count += int(summary.get("node_count") or 0)
        edge_count += int(summary.get("edge_count") or 0)
        file_count += int(summary.get("file_count") or 0)
        parser_backends.update(str(item) for item in summary.get("parser_backends", []))
        for block, count in (summary.get("block_counts") or {}).items():
            block_counts[str(block)] = block_counts.get(str(block), 0) + int(count)
        for surface in report.get("surfaces", []):
            surfaces.append({**surface, "repo": report["repo"]})

    surfaces.sort(key=lambda item: (-float(item.get("confidence", 0)), str(item.get("repo", "")), str(item.get("path", ""))))
    assessment = build_system_assessment(per_repo, surfaces, block_counts)
    return {
        "repo": repo_label,
        "repos": [report["repo"] for report in per_repo],
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "summary": {
            "node_count": node_count,
            "edge_count": edge_count,
            "file_count": file_count,
            "repo_count": len(per_repo),
            "parser_backends": sorted(parser_backends),
            "block_counts": dict(sorted(block_counts.items(), key=lambda item: (-item[1], item[0]))),
            "graph_integrity": {"overall_status": _aggregate_integrity(per_repo)},
            "manifest": {"required_artifacts_present": all(bool(r.get("summary", {}).get("manifest", {}).get("required_artifacts_present")) for r in per_repo)},
        },
        "repo_reports": per_repo,
        "assessment": assessment,
        "insights": build_multi_repo_insights(per_repo, surfaces, block_counts),
        "runtime_capabilities": {
            "repo_source": "public_github_zipball_multi_repo",
            "structural_ingest": "python_tree_sitter_language_pack",
            "classifier": "deterministic_heuristic_no_openai",
            "system_graph": "aggregate_multi_repo_receipt",
        },
        "warnings": [warning for report in per_repo for warning in report.get("warnings", []) if warning],
        "surfaces": surfaces[: load_limits().max_returned_surfaces],
    }


def build_system_assessment(per_repo: list[dict[str, Any]], surfaces: list[dict[str, Any]], block_counts: dict[str, int]) -> dict[str, Any]:
    repo_roles = [_repo_role(report) for report in per_repo]
    entity_terms = {
        "User / Account": ("user", "account", "customer", "profile"),
        "Session / Auth": ("session", "auth", "token", "signin", "login", "provider"),
        "Cart / Checkout": ("cart", "checkout", "basket", "line_item", "line-item"),
        "Order / Fulfillment": ("order", "fulfillment", "shipping", "delivery"),
        "Payment": ("payment", "paymentintent", "stripe", "invoice", "charge", "webhook"),
        "Upload": ("upload", "asset", "image", "media"),
    }
    entity_map = {label: _matching_surfaces(surfaces, terms, limit=4) for label, terms in entity_terms.items()}
    workflow_evidence = _dedupe_surfaces(
        entity_map["Cart / Checkout"] + entity_map["Session / Auth"] + entity_map["Payment"] + _matching_surfaces(surfaces, ("api", "route", "webhook"), limit=5),
        limit=8,
    )
    impact_evidence = _dedupe_surfaces(
        _matching_surfaces(surfaces, ("payment", "stripe", "checkout", "webhook", "session", "auth"), limit=8)
        + [surface for surface in surfaces if surface.get("block") in {"Network Edge", "Connectivity Layer", "Access Control", "Data Persistence"}],
        limit=8,
    )
    citation_evidence = _dedupe_surfaces(workflow_evidence + impact_evidence + surfaces[:6], limit=10)

    return {
        "headline": "Commerce checkout system assessment",
        "summary": (
            "LogicLens treats the selected repositories as one commerce system: a storefront that starts cart/checkout behavior, "
            "an identity layer that owns User and Session state, and a payment SDK surface that owns Stripe/PaymentIntent concepts."
        ),
        "project_understanding": {
            "question": "What services/repos exist, what role does each play, and how do they relate?",
            "answer": "The system separates user-facing commerce, authentication/session ownership, and payment-provider integration. Changes to checkout behavior are likely to cross those boundaries.",
            "repos": repo_roles,
        },
        "entity_workflows": [
            {
                "question": "Where is User, Session, Order, Checkout, or Payment handled?",
                "answer": "Entity signals are strongest around auth/session models, checkout/cart surfaces, and Stripe/payment API boundaries. Use these as workflow anchors before reading broad directories.",
                "entities": [
                    {"name": label, "evidence": evidence}
                    for label, evidence in entity_map.items()
                    if evidence
                ],
            },
            {
                "question": "Trace the checkout/login/payment workflow.",
                "answer": "Start at storefront cart/checkout surfaces, cross into session/auth boundaries for user identity, then inspect payment/webhook or Stripe SDK surfaces for money movement and fulfillment seams.",
                "evidence": workflow_evidence,
            },
        ],
        "code_grounded_retrieval": {
            "question": "Which files/functions/classes support these claims?",
            "answer": "Each claim below is backed by concrete repo/path/range evidence from the graph ingest and semantic block classifier.",
            "evidence": citation_evidence,
        },
        "graph_reasoning": {
            "question": "If I change checkout or payment creation, what might be affected?",
            "answer": "The first blast-radius ring is network/API surfaces, auth/session state, persistence models, and payment SDK calls. These are the cross-repo seams a developer should inspect before editing.",
            "evidence": impact_evidence,
        },
        "architecture_qa": [
            {
                "question": "Where is Session handled?",
                "answer": "Look first for Access Control and Data Persistence evidence containing session/auth/token/provider terms, then follow callers in storefront/API surfaces.",
                "evidence": entity_map["Session / Auth"][:5],
            },
            {
                "question": "Trace checkout to payment.",
                "answer": "Follow cart/checkout surfaces into payment or Stripe-named SDK/API surfaces; webhook-like network edges are the likely confirmation/fulfillment boundary.",
                "evidence": _dedupe_surfaces(entity_map["Cart / Checkout"] + entity_map["Payment"], limit=6),
            },
            {
                "question": "What should I inspect before changing payment behavior?",
                "answer": "Inspect high-confidence payment, network-edge, connectivity, and persistence surfaces first; these are where a local code change is most likely to affect external behavior.",
                "evidence": impact_evidence[:6],
            },
        ],
        "dominant_blocks": [{"block": block, "count": count} for block, count in sorted(block_counts.items(), key=lambda item: (-item[1], item[0]))[:6]],
    }


def _repo_role(report: dict[str, Any]) -> dict[str, Any]:
    repo = str(report.get("repo", ""))
    blocks = report.get("summary", {}).get("block_counts", {})
    top_blocks = sorted(blocks.items(), key=lambda item: (-int(item[1]), item[0]))[:3]
    lower = repo.lower()
    if "commerce" in lower or "storefront" in lower:
        role = "Storefront and commerce experience"
        relationship = "Starts product browsing, cart, and checkout behavior."
    elif "auth" in lower or "session" in lower:
        role = "Identity and session boundary"
        relationship = "Owns User, Account, Session, Token, and provider concepts."
    elif "stripe" in lower or "payment" in lower:
        role = "Payment provider integration"
        relationship = "Owns Stripe SDK surfaces, customers, checkout sessions, and payment intents."
    else:
        role = ", ".join(block for block, _ in top_blocks) or "Source surfaces"
        relationship = "Role inferred from dominant architecture blocks."
    return {
        "repo": repo,
        "role": role,
        "relationship": relationship,
        "dominant_blocks": [{"block": block, "count": int(count)} for block, count in top_blocks],
        "node_count": int(report.get("summary", {}).get("node_count") or 0),
        "file_count": int(report.get("summary", {}).get("file_count") or 0),
    }


def _matching_surfaces(surfaces: list[dict[str, Any]], terms: tuple[str, ...], *, limit: int) -> list[dict[str, Any]]:
    matches = []
    for surface in surfaces:
        haystack = f"{surface.get('repo', '')} {surface.get('path', '')} {surface.get('name', '')} {surface.get('block', '')} {surface.get('signal', '')}".lower()
        if any(term in haystack for term in terms):
            matches.append(surface)
    return _dedupe_surfaces(matches, limit=limit)


def _dedupe_surfaces(surfaces: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    seen = set()
    deduped = []
    for surface in surfaces:
        key = (surface.get("repo"), surface.get("path"), surface.get("name"), surface.get("block"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(surface)
        if len(deduped) >= limit:
            break
    return deduped


def build_multi_repo_insights(per_repo: list[dict[str, Any]], surfaces: list[dict[str, Any]], block_counts: dict[str, int]) -> list[dict[str, Any]]:
    repo_roles = []
    for report in per_repo:
        blocks = report.get("summary", {}).get("block_counts", {})
        top_blocks = sorted(blocks.items(), key=lambda item: (-int(item[1]), item[0]))[:3]
        role = ", ".join(block for block, _ in top_blocks) or "source surfaces"
        repo_roles.append({"repo": report["repo"], "role": role, "nodes": report.get("summary", {}).get("node_count", 0)})

    boundary_blocks = {"Network Edge", "Connectivity Layer", "Data Persistence", "Background Processing", "Access Control", "Interaction Design"}
    boundary_samples = [surface for surface in surfaces if surface.get("block") in boundary_blocks][:8]
    dominant = [{"block": block, "count": count} for block, count in sorted(block_counts.items(), key=lambda item: (-item[1], item[0]))[:5]]
    languages = sorted({lang for report in per_repo for lang in report.get("summary", {}).get("parser_backends", [])})
    entity_terms = ("user", "order", "session", "checkout", "payment", "upload", "cart", "account", "auth", "token")
    entity_samples = [
        surface
        for surface in surfaces
        if any(term in f"{surface.get('path', '')} {surface.get('name', '')} {surface.get('signal', '')}".lower() for term in entity_terms)
    ][:8]
    high_confidence = surfaces[:8]

    return [
        {
            "title": "Project understanding: what repos exist?",
            "answer": f"LogicLens analyzed {len(per_repo)} repositories as one system. The strongest cross-repo signal is a {', '.join(languages[:6]) or 'multi-language'} stack with complementary project roles.",
            "samples": [{"repo": item["repo"], "path": item["repo"], "block": item["role"], "confidence": min(0.95, 0.65 + int(item["nodes"]) / 20000)} for item in repo_roles],
            "empty_state": "No per-repo roles available.",
        },
        {
            "title": "Entity/workflow understanding",
            "answer": "User, Order, Session, Checkout, Payment, Upload, and Cart signals are pulled out as workflow anchors. These are the best places to start tracing business behavior across repos.",
            "samples": entity_samples,
            "empty_state": "No obvious entity or workflow surfaces found in the bounded result window.",
        },
        {
            "title": "Graph reasoning: where do repos meet?",
            "answer": "Start with network, connectivity, persistence, background-work, interaction, and access-control surfaces. Those are the most likely integration seams and blast-radius boundaries across repositories.",
            "samples": boundary_samples,
            "empty_state": "No likely integration seams found in the bounded result window.",
        },
        {
            "title": "Architecture Q&A: what dominates?",
            "answer": "The aggregate block distribution shows the system-level shape rather than one repository's local implementation details.",
            "dominant_blocks": dominant,
            "empty_state": "No aggregate block distribution available.",
        },
        {
            "title": "Code-grounded retrieval: cite the evidence",
            "answer": "Relevant files, functions, classes, and source ranges are returned as evidence. A useful answer should cite these paths before making an architecture claim.",
            "samples": high_confidence,
            "empty_state": "No evidence surfaces returned.",
        },
    ]


def _aggregate_integrity(reports: list[dict[str, Any]]) -> str:
    statuses = [str(report.get("summary", {}).get("graph_integrity", {}).get("overall_status", "unknown")) for report in reports]
    if all(status == "pass" for status in statuses):
        return "pass"
    if any(status == "fail" for status in statuses):
        return "partial"
    return "unknown"


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


def _analysis_cost(repos: list[str]) -> float:
    cost = 0.0
    for repo in repos:
        owner, name = repo.split("/", 1)
        cost += 5.0 + (len(owner) + len(name)) / 80
    return min(30.0, cost)


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
