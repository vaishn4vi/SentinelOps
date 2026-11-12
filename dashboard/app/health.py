"""Remote health checks against a service's health_check_url."""

from __future__ import annotations

import time

import requests
from flask import current_app

from .extensions import db
from .models import Service, utcnow


def check_service_health(service: Service) -> dict:
    """Call the service health endpoint and persist the result."""
    if not service.health_check_url:
        return {"ok": False, "status": "unknown", "message": "No health check URL configured."}

    timeout = current_app.config.get("HEALTH_CHECK_TIMEOUT", 5)
    started = time.perf_counter()
    try:
        response = requests.get(service.health_check_url, timeout=timeout)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        ok = response.status_code == 200
        result = {
            "ok": ok,
            "status": "healthy" if ok else "unhealthy",
            "http_status": response.status_code,
            "response_ms": elapsed_ms,
            "message": f"HTTP {response.status_code} in {elapsed_ms} ms",
        }
    except requests.RequestException as exc:
        current_app.logger.warning("Health check for %s failed: %s", service.name, exc)
        result = {
            "ok": False,
            "status": "unreachable",
            "message": f"Could not reach {service.health_check_url}: {exc.__class__.__name__}",
        }

    service.last_health_status = result["status"]
    service.last_health_check_at = utcnow()
    db.session.commit()
    return result
