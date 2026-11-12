"""Jinja filters and globals used across templates."""

from __future__ import annotations

from datetime import datetime

from flask import Flask

from .models import (
    DEPLOYMENT_STATUSES,
    ENVIRONMENTS,
    INCIDENT_SEVERITIES,
    INCIDENT_STATUSES,
    SERVICE_STATUSES,
    utcnow,
)

STATUS_BADGES = {
    "success": "success",
    "healthy": "success",
    "active": "success",
    "resolved": "success",
    "failed": "danger",
    "critical": "danger",
    "unhealthy": "danger",
    "unreachable": "danger",
    "rolled_back": "warning",
    "degraded": "warning",
    "high": "warning",
    "investigating": "warning",
    "in_progress": "info",
    "open": "info",
    "medium": "info",
    "low": "secondary",
    "inactive": "secondary",
    "unknown": "secondary",
}


def register_template_helpers(app: Flask) -> None:
    @app.template_filter("badge")
    def badge_class(value: str | None) -> str:
        return STATUS_BADGES.get((value or "").lower(), "secondary")

    @app.template_filter("label")
    def humanize(value: str | None) -> str:
        return (value or "—").replace("_", " ").title()

    @app.template_filter("datetime")
    def format_datetime(value: datetime | None, fmt: str = "%d %b %Y, %H:%M") -> str:
        return value.strftime(fmt) + " UTC" if value else "—"

    @app.template_filter("timeago")
    def timeago(value: datetime | None) -> str:
        if not value:
            return "—"
        seconds = int((utcnow() - value).total_seconds())
        if seconds < 60:
            return "just now"
        for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
            if seconds >= size:
                return f"{seconds // size}{unit} ago"
        return "just now"

    @app.template_filter("duration")
    def duration(seconds: int | None) -> str:
        if seconds is None:
            return "—"
        minutes, secs = divmod(int(seconds), 60)
        return f"{minutes}m {secs:02d}s" if minutes else f"{secs}s"

    @app.context_processor
    def inject_constants():
        return {
            "DEPLOYMENT_STATUSES": DEPLOYMENT_STATUSES,
            "ENVIRONMENTS": ENVIRONMENTS,
            "SERVICE_STATUSES": SERVICE_STATUSES,
            "INCIDENT_SEVERITIES": INCIDENT_SEVERITIES,
            "INCIDENT_STATUSES": INCIDENT_STATUSES,
        }
