"""Dashboard overview, deployment history and deployment details."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import login_required
from sqlalchemy import or_

from ..extensions import db
from ..models import DEPLOYMENT_STATUSES, Deployment, Incident, Service
from ..stats import chart_payload, full_stats

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return redirect(url_for("main.dashboard"))


@main_bp.route("/dashboard")
@login_required
def dashboard():
    stats = full_stats()
    recent = (
        Deployment.query.order_by(Deployment.created_at.desc()).limit(8).all()
    )
    open_incidents = (
        Incident.query.filter(Incident.status != "resolved")
        .order_by(Incident.created_at.desc())
        .limit(5)
        .all()
    )
    return render_template(
        "dashboard.html", stats=stats, recent=recent, open_incidents=open_incidents
    )


@main_bp.route("/dashboard/chart-data")
@login_required
def chart_data():
    return jsonify(chart_payload())


@main_bp.route("/deployments")
@login_required
def deployments():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "").strip()
    service_id = request.args.get("service_id", type=int)
    search = request.args.get("q", "").strip()

    query = Deployment.query.join(Service)
    if status in DEPLOYMENT_STATUSES:
        query = query.filter(Deployment.status == status)
    if service_id:
        query = query.filter(Deployment.service_id == service_id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Deployment.commit_id.ilike(like),
                Deployment.commit_author.ilike(like),
                Deployment.commit_message.ilike(like),
                Deployment.image_tag.ilike(like),
                Service.name.ilike(like),
            )
        )

    pagination = query.order_by(Deployment.created_at.desc()).paginate(
        page=page, per_page=current_app.config["ITEMS_PER_PAGE"], error_out=False
    )
    services = Service.query.order_by(Service.name).all()
    return render_template(
        "deployments/list.html",
        pagination=pagination,
        services=services,
        filters={"status": status, "service_id": service_id, "q": search},
    )


@main_bp.route("/deployments/<int:deployment_id>")
@login_required
def deployment_detail(deployment_id: int):
    deployment = db.session.get(Deployment, deployment_id) or abort(404)
    previous = (
        Deployment.query.filter(
            Deployment.service_id == deployment.service_id,
            Deployment.created_at < deployment.created_at,
        )
        .order_by(Deployment.created_at.desc())
        .first()
    )
    service_history = (
        Deployment.query.filter_by(service_id=deployment.service_id)
        .order_by(Deployment.created_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "deployments/detail.html",
        deployment=deployment,
        previous=previous,
        service_history=service_history,
        incidents=deployment.incidents.all(),
    )
