"""Aggregations used by the dashboard UI and the /api/stats endpoint.

Aggregation by date is done in Python so it behaves identically on MySQL
(production) and SQLite (tests).
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import timedelta

from sqlalchemy import func

from .extensions import db
from .models import Deployment, Incident, Service, utcnow


def deployment_summary(service_id: int | None = None) -> dict:
    query = db.session.query(Deployment.status, func.count(Deployment.id))
    if service_id is not None:
        query = query.filter(Deployment.service_id == service_id)
    counts = dict(query.group_by(Deployment.status).all())

    total = sum(counts.values())
    successful = counts.get("success", 0)
    failed = counts.get("failed", 0)
    rolled_back = counts.get("rolled_back", 0)
    in_progress = counts.get("in_progress", 0)
    finished = successful + failed + rolled_back
    success_rate = round(successful / finished * 100, 2) if finished else 0.0

    return {
        "total_deployments": total,
        "successful_deployments": successful,
        "failed_deployments": failed,
        "rollback_count": rolled_back,
        "in_progress_deployments": in_progress,
        "success_percentage": success_rate,
    }


def full_stats() -> dict:
    stats = deployment_summary()
    stats["total_services"] = db.session.query(func.count(Service.id)).scalar() or 0
    stats["open_incidents"] = (
        db.session.query(func.count(Incident.id)).filter(Incident.status != "resolved").scalar()
        or 0
    )
    last = Deployment.query.order_by(Deployment.created_at.desc()).first()
    stats["last_deployment"] = last.to_dict() if last else None
    return stats


def daily_trend(days: int = 14) -> dict:
    """Deployments per day per status for the last ``days`` days."""
    today = utcnow().date()
    start = today - timedelta(days=days - 1)
    buckets: "OrderedDict[str, dict]" = OrderedDict(
        ((start + timedelta(days=i)).isoformat(), {"success": 0, "failed": 0, "rolled_back": 0})
        for i in range(days)
    )
    rows = (
        db.session.query(Deployment.created_at, Deployment.status)
        .filter(Deployment.created_at >= start)
        .all()
    )
    for created_at, status in rows:
        key = created_at.date().isoformat()
        if key in buckets and status in buckets[key]:
            buckets[key][status] += 1

    return {
        "labels": list(buckets.keys()),
        "success": [b["success"] for b in buckets.values()],
        "failed": [b["failed"] for b in buckets.values()],
        "rolled_back": [b["rolled_back"] for b in buckets.values()],
    }


def per_service_breakdown(limit: int = 8) -> dict:
    rows = (
        db.session.query(Service.name, Deployment.status, func.count(Deployment.id))
        .join(Deployment, Deployment.service_id == Service.id)
        .group_by(Service.name, Deployment.status)
        .all()
    )
    data: dict[str, dict] = {}
    for name, status, count in rows:
        data.setdefault(name, {"success": 0, "failed": 0, "rolled_back": 0, "in_progress": 0})
        data[name][status] = count
    ranked = sorted(data.items(), key=lambda kv: sum(kv[1].values()), reverse=True)[:limit]
    return {
        "labels": [name for name, _ in ranked],
        "success": [v["success"] for _, v in ranked],
        "failed": [v["failed"] + v["rolled_back"] for _, v in ranked],
    }


def chart_payload() -> dict:
    summary = deployment_summary()
    return {
        "trend": daily_trend(),
        "status": {
            "labels": ["Success", "Failed", "Rolled back", "In progress"],
            "values": [
                summary["successful_deployments"],
                summary["failed_deployments"],
                summary["rollback_count"],
                summary["in_progress_deployments"],
            ],
        },
        "services": per_service_breakdown(),
    }
