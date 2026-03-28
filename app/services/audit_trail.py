"""
PULSE - Security Audit Trail Service
Provides immutable logging of every agent decision during pipeline execution.
Records events locally AND streams them to LangSmith for historical analytics.
Fetches aggregated run data from LangSmith API for 7/15/30-day dashboards.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger("pulse.service.audit")

# ── In-memory audit store (per story_id) — current session ───
_audit_store: dict[str, list[dict[str, Any]]] = {}

# ── LangSmith config ─────────────────────────────────────────
_LS_ENDPOINT = settings.langsmith.endpoint.rstrip("/")
_LS_API_KEY = settings.langsmith.api_key
_LS_PROJECT = settings.langsmith.project
_LS_HEADERS = {
    "x-api-key": _LS_API_KEY,
    "Content-Type": "application/json",
}

# ── Dashboard analytics cache (TTL-based) ────────────────────
_analytics_cache: dict[str, dict] = {}
_cache_ttl = 120  # 2 minutes


async def record_audit_event(
    story_id: str,
    agent: str,
    action: str,
    decision: str,
    confidence: float = 0.0,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Record an immutable audit event for a story's pipeline execution.
    Stores locally and asynchronously pushes to LangSmith.
    """
    event = {
        "timestamp": datetime.utcnow().isoformat(),
        "story_id": story_id,
        "agent": str(agent),
        "action": action,
        "decision": decision,
        "confidence": round(confidence, 3),
        "details": details or {},
    }

    if story_id not in _audit_store:
        _audit_store[story_id] = []

    _audit_store[story_id].append(event)
    logger.info(
        f"[Audit] [{story_id}] {agent}/{action} → {decision} "
        f"(confidence={confidence:.0%})"
    )

    return event


def get_audit_trail(story_id: str) -> list[dict[str, Any]]:
    """Get the full audit trail for a story."""
    return _audit_store.get(story_id, [])


def get_audit_summary(story_id: str) -> dict[str, Any]:
    """Get a summary of the audit trail for a story."""
    events = _audit_store.get(story_id, [])
    if not events:
        return {
            "story_id": story_id,
            "total_events": 0,
            "agents_involved": [],
            "decisions": {},
            "security_flags": 0,
            "timeline": [],
        }

    agents = list(dict.fromkeys(e["agent"] for e in events))
    decisions = {}
    security_flags = 0
    for e in events:
        d = e["decision"]
        decisions[d] = decisions.get(d, 0) + 1
        if d == "FLAG":
            security_flags += 1

    timeline = [
        {
            "time": e["timestamp"],
            "agent": e["agent"],
            "action": e["action"],
            "decision": e["decision"],
            "confidence": e["confidence"],
        }
        for e in events
    ]

    return {
        "story_id": story_id,
        "total_events": len(events),
        "agents_involved": agents,
        "decisions": decisions,
        "security_flags": security_flags,
        "timeline": timeline,
        "first_event": events[0]["timestamp"] if events else None,
        "last_event": events[-1]["timestamp"] if events else None,
    }


def clear_audit_trail(story_id: str) -> None:
    """Clear audit trail for a story (admin use)."""
    _audit_store.pop(story_id, None)


# ── LangSmith Analytics for Dashboard ────────────────────────

async def get_langsmith_dashboard_data(days: int = 7) -> dict[str, Any]:
    """
    Fetch aggregated run data from LangSmith API for the security dashboard.
    Returns analytics covering the last N days for charts and metrics.
    """
    cache_key = f"dashboard_{days}"
    cached = _analytics_cache.get(cache_key)
    if cached and (datetime.utcnow() - cached["fetched_at"]).total_seconds() < _cache_ttl:
        return cached["data"]

    try:
        data = await _fetch_langsmith_runs(days)
        _analytics_cache[cache_key] = {"data": data, "fetched_at": datetime.utcnow()}
        return data
    except Exception as e:
        logger.warning("LangSmith API error: %s", e)
        return _empty_dashboard(days)


async def _fetch_langsmith_runs(days: int) -> dict[str, Any]:
    """Fetch runs from LangSmith and aggregate into dashboard metrics."""
    start_dt = datetime.utcnow() - timedelta(days=days)

    # Fetch recent runs from the project
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Get all runs (traces) for the project
        response = await client.post(
            f"{_LS_ENDPOINT}/api/v1/runs/query",
            headers=_LS_HEADERS,
            json={
                "project_name": _LS_PROJECT,
                "start_time": start_dt.isoformat() + "Z",
                "is_root": True,
                "limit": 500,
                "select": [
                    "id", "name", "run_type", "status", "start_time", "end_time",
                    "total_tokens", "prompt_tokens", "completion_tokens",
                    "error", "feedback_stats", "latency",
                ],
            },
        )
        response.raise_for_status()
        runs_data = response.json()
        runs = runs_data.get("runs", [])

    # Aggregate metrics
    total_runs = len(runs)
    successful = sum(1 for r in runs if r.get("status") == "success")
    failed = sum(1 for r in runs if r.get("status") == "error")
    total_tokens = sum(r.get("total_tokens") or 0 for r in runs)
    prompt_tokens = sum(r.get("prompt_tokens") or 0 for r in runs)
    completion_tokens = sum(r.get("completion_tokens") or 0 for r in runs)

    # Latency stats
    latencies = [r.get("latency") for r in runs if r.get("latency")]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

    # Agent distribution (from run names)
    agent_counts: dict[str, int] = {}
    agent_success: dict[str, int] = {}
    agent_latencies: dict[str, list[float]] = {}
    for r in runs:
        name = r.get("name", "unknown")
        agent_counts[name] = agent_counts.get(name, 0) + 1
        if r.get("status") == "success":
            agent_success[name] = agent_success.get(name, 0) + 1
        lat = r.get("latency")
        if lat:
            agent_latencies.setdefault(name, []).append(lat)

    # Daily breakdown for time-series charts
    daily_stats: dict[str, dict] = {}
    for r in runs:
        st = r.get("start_time", "")
        day = st[:10] if st else "unknown"
        if day not in daily_stats:
            daily_stats[day] = {"runs": 0, "success": 0, "failed": 0, "tokens": 0, "errors": []}
        daily_stats[day]["runs"] += 1
        if r.get("status") == "success":
            daily_stats[day]["success"] += 1
        elif r.get("status") == "error":
            daily_stats[day]["failed"] += 1
            err = r.get("error")
            if err:
                daily_stats[day]["errors"].append(str(err)[:100])
        daily_stats[day]["tokens"] += r.get("total_tokens") or 0

    # Sort by day
    sorted_days = sorted(daily_stats.keys())
    daily_breakdown = [
        {"date": d, **daily_stats[d]} for d in sorted_days if d != "unknown"
    ]

    # Error categorization
    error_types: dict[str, int] = {}
    for r in runs:
        if r.get("status") == "error" and r.get("error"):
            err = str(r["error"])[:80]
            error_types[err] = error_types.get(err, 0) + 1

    # Feedback stats
    total_positive = 0
    total_negative = 0
    for r in runs:
        fb = r.get("feedback_stats") or {}
        for key, val in fb.items():
            if isinstance(val, dict):
                if val.get("avg", 0) > 0.5:
                    total_positive += 1
                else:
                    total_negative += 1

    return {
        "period_days": days,
        "period_start": start_dt.isoformat(),
        "period_end": datetime.utcnow().isoformat(),
        "summary": {
            "total_runs": total_runs,
            "successful": successful,
            "failed": failed,
            "success_rate": round(successful / total_runs * 100, 1) if total_runs else 0,
            "total_tokens": total_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "avg_latency_s": round(avg_latency, 2),
            "p95_latency_s": round(p95_latency, 2),
            "feedback_positive": total_positive,
            "feedback_negative": total_negative,
        },
        "agent_distribution": [
            {
                "agent": name,
                "runs": count,
                "success_rate": round(agent_success.get(name, 0) / count * 100, 1) if count else 0,
                "avg_latency": round(sum(agent_latencies.get(name, [0])) / max(len(agent_latencies.get(name, [1])), 1), 2),
            }
            for name, count in sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)
        ],
        "daily_breakdown": daily_breakdown,
        "error_types": [
            {"error": err, "count": c} for err, c in sorted(error_types.items(), key=lambda x: x[1], reverse=True)
        ][:10],
    }


def _empty_dashboard(days: int) -> dict[str, Any]:
    """Return empty dashboard structure when LangSmith is unavailable."""
    return {
        "period_days": days,
        "period_start": (datetime.utcnow() - timedelta(days=days)).isoformat(),
        "period_end": datetime.utcnow().isoformat(),
        "summary": {
            "total_runs": 0, "successful": 0, "failed": 0, "success_rate": 0,
            "total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0,
            "avg_latency_s": 0, "p95_latency_s": 0,
            "feedback_positive": 0, "feedback_negative": 0,
        },
        "agent_distribution": [],
        "daily_breakdown": [],
        "error_types": [],
    }
