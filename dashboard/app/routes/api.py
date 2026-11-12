"""REST API consumed by Jenkins (and any other CI system).

Authentication: send the key configured in SENTINELOPS_API_KEY in the
``X-API-Key`` header (or ``Authorization: Bearer <key>``).

Endpoints
---------
GET  /api/health                 liveness / DB connectivity (no auth)
GET  /api/stats                  deployment statistics
GET  /api/deployments            list deployments (filters + pagination)
GET  /api/deployments/<id>       single deployment
POST /api/deployments            record a deployment
GET  /api/services               list services
"""

from __future__ import annotations

import hmac
from functools import wraps

from flask import Blueprint, current_app, jsonify, request, url_for
from flask_login import current_user
from sqlalchemy import text

from ..deployments import record_deployment
from ..extensions import db
from ..models import DEPLOYMENT_STATUSES, Deployment, Service
from ..stats import full_stats
from ..validators import ValidationError, normalize_status, validate_deployment_payload

api_bp = Blueprint("api", __name__, url_prefix="/api")

MAX_LIMIT = 200


def _provided_key() -> str:
    key = request.headers.get("X-API-Key", "")
    if not key:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("bearer "):
            key = auth[7:]
    return key.strip()


def require_api_key(allow_session: bool = False):
    """Require a valid API key. Read endpoints also accept a logged-in browser session."""

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            if allow_session and current_user.is_authenticated:
                return view(*args, **kwargs)
            expected = current_app.config.get("SENTINELOPS_API_KEY") or ""
            if not expected:
                current_app.logger.error("SENTINELOPS_API_KEY is not configured; API locked.")
                return jsonify(error="api_not_configured", message="API key is not configured on the server."), 503
            provided = _provided_key()
            if not provided or not hmac.compare_digest(provided.encode(), expected.encode()):
                return jsonify(error="unauthorized", message="Missing or invalid API key."), 401
            return view(*args, **kwargs)

        return wrapper

    return decorator


@api_bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok", database="up")
    except Exception as exc:  # noqa: BLE001 - report any DB failure
        current_app.logger.error("Health check DB failure: %s", exc)
        db.session.rollback()
        return jsonify(status="degraded", database="down"), 503


@api_bp.get("/stats")
@require_api_key(allow_session=True)
def stats():
    return jsonify(full_stats())


@api_bp.get("/deployments")
@require_api_key(allow_session=True)
def list_deployments():
    try:
        limit = min(max(int(request.args.get("limit", 50)), 1), MAX_LIMIT)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return jsonify(error="bad_request", message="limit and offset must be integers."), 400

    query = Deployment.query.join(Service)
    status = request.args.get("status")
    if status:
        status = normalize_status(status)
        if status not in DEPLOYMENT_STATUSES:
            return jsonify(error="bad_request", message=f"status must be one of {list(DEPLOYMENT_STATUSES)}"), 400
        query = query.filter(Deployment.status == status)
    service_name = request.args.get("service_name")
    if service_name:
        query = query.filter(Service.name == service_name)

    total = query.count()
    items = query.order_by(Deployment.created_at.desc(), Deployment.id.desc()).offset(offset).limit(limit).all()
    return jsonify(
        total=total,
        limit=limit,
        offset=offset,
        deployments=[d.to_dict() for d in items],
    )


@api_bp.get("/deployments/<int:deployment_id>")
@require_api_key(allow_session=True)
def get_deployment(deployment_id: int):
    deployment = db.session.get(Deployment, deployment_id)
    if not deployment:
        return jsonify(error="not_found", message=f"Deployment {deployment_id} not found."), 404
    payload = deployment.to_dict()
    payload["incidents"] = [i.to_dict() for i in deployment.incidents]
    return jsonify(payload)


@api_bp.post("/deployments")
@require_api_key()
def create_deployment():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(error="bad_request", message="Body must be valid JSON with Content-Type: application/json."), 400
    try:
        data = validate_deployment_payload(payload)
    except ValidationError as exc:
        return jsonify(error="validation_error", message="Invalid deployment payload.", fields=exc.errors), 422

    deployment, incident, service_created = record_deployment(data)
    current_app.logger.info(
        "Deployment recorded: service=%s build=%s status=%s",
        data["service_name"], deployment.build_number, deployment.status,
    )
    body = {
        "message": "Deployment recorded.",
        "deployment": deployment.to_dict(),
        "service_created": service_created,
        "incident_id": incident.id if incident else None,
        "dashboard_url": url_for("main.deployment_detail", deployment_id=deployment.id, _external=True),
    }
    response = jsonify(body)
    response.status_code = 201
    response.headers["Location"] = url_for("api.get_deployment", deployment_id=deployment.id)
    return response


@api_bp.get("/services")
@require_api_key(allow_session=True)
def list_services():
    return jsonify(services=[s.to_dict() for s in Service.query.order_by(Service.name).all()])
