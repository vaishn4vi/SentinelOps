"""Services CRUD and on-demand health checks."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..extensions import db
from ..health import check_service_health
from ..models import Incident, Service
from ..stats import deployment_summary
from ..validators import ValidationError, validate_service_form

services_bp = Blueprint("services", __name__, url_prefix="/services")


def _get_service(service_id: int) -> Service:
    return db.session.get(Service, service_id) or abort(404)


def _name_taken(name: str, exclude_id: int | None = None) -> bool:
    query = Service.query.filter(Service.name == name)
    if exclude_id:
        query = query.filter(Service.id != exclude_id)
    return db.session.query(query.exists()).scalar()


@services_bp.route("/")
@login_required
def list_services():
    services = Service.query.order_by(Service.name).all()
    summaries = {s.id: deployment_summary(s.id) for s in services}
    return render_template("services/list.html", services=services, summaries=summaries)


@services_bp.route("/<int:service_id>")
@login_required
def detail(service_id: int):
    service = _get_service(service_id)
    return render_template(
        "services/detail.html",
        service=service,
        summary=deployment_summary(service.id),
        deployments=service.deployments.limit(15).all(),
        incidents=service.incidents.order_by(Incident.created_at.desc()).limit(10).all(),
    )


@services_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    errors: dict[str, str] = {}
    if request.method == "POST":
        try:
            data = validate_service_form(request.form)
            if _name_taken(data["name"]):
                errors["name"] = "A service with this name already exists."
            else:
                service = Service(**data)
                db.session.add(service)
                db.session.commit()
                flash(f"Service '{service.name}' created.", "success")
                return redirect(url_for("services.detail", service_id=service.id))
        except ValidationError as exc:
            errors = exc.errors
        return render_template("services/form.html", errors=errors, form=request.form, service=None), 400
    return render_template("services/form.html", errors=errors, form={}, service=None)


@services_bp.route("/<int:service_id>/edit", methods=["GET", "POST"])
@login_required
def edit(service_id: int):
    service = _get_service(service_id)
    errors: dict[str, str] = {}
    if request.method == "POST":
        try:
            data = validate_service_form(request.form)
            if _name_taken(data["name"], exclude_id=service.id):
                errors["name"] = "A service with this name already exists."
            else:
                for key, value in data.items():
                    setattr(service, key, value)
                db.session.commit()
                flash(f"Service '{service.name}' updated.", "success")
                return redirect(url_for("services.detail", service_id=service.id))
        except ValidationError as exc:
            errors = exc.errors
        return render_template("services/form.html", errors=errors, form=request.form, service=service), 400
    return render_template("services/form.html", errors=errors, form=service.__dict__, service=service)


@services_bp.route("/<int:service_id>/delete", methods=["POST"])
@login_required
def delete(service_id: int):
    service = _get_service(service_id)
    name = service.name
    db.session.delete(service)
    db.session.commit()
    flash(f"Service '{name}' and its deployment history were deleted.", "info")
    return redirect(url_for("services.list_services"))


@services_bp.route("/<int:service_id>/health-check", methods=["POST"])
@login_required
def health_check(service_id: int):
    service = _get_service(service_id)
    result = check_service_health(service)
    category = "success" if result["ok"] else ("warning" if result["status"] == "unknown" else "danger")
    flash(f"{service.name}: {result['status'].upper()} — {result['message']}", category)
    return redirect(request.referrer or url_for("services.detail", service_id=service.id))
