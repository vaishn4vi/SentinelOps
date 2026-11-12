"""Incidents CRUD."""

from __future__ import annotations

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import login_required

from ..extensions import db
from ..models import INCIDENT_SEVERITIES, INCIDENT_STATUSES, Deployment, Incident, Service, utcnow
from ..validators import ValidationError, validate_incident_form

incidents_bp = Blueprint("incidents", __name__, url_prefix="/incidents")


def _get_incident(incident_id: int) -> Incident:
    return db.session.get(Incident, incident_id) or abort(404)


def _form_context():
    return {
        "services": Service.query.order_by(Service.name).all(),
        "deployments": Deployment.query.order_by(Deployment.created_at.desc()).limit(50).all(),
    }


def _check_references(data: dict, errors: dict) -> None:
    if data["service_id"] and not db.session.get(Service, data["service_id"]):
        errors["service_id"] = "Selected service does not exist."
    if data["deployment_id"]:
        deployment = db.session.get(Deployment, data["deployment_id"])
        if not deployment:
            errors["deployment_id"] = "Selected deployment does not exist."
        elif not data["service_id"]:
            data["service_id"] = deployment.service_id


def _apply_status_change(incident: Incident, new_status: str) -> None:
    if new_status == "resolved" and incident.status != "resolved":
        incident.resolved_at = utcnow()
    elif new_status != "resolved":
        incident.resolved_at = None


@incidents_bp.route("/")
@login_required
def list_incidents():
    page = request.args.get("page", 1, type=int)
    status = request.args.get("status", "").strip()
    severity = request.args.get("severity", "").strip()
    query = Incident.query
    if status in INCIDENT_STATUSES:
        query = query.filter(Incident.status == status)
    if severity in INCIDENT_SEVERITIES:
        query = query.filter(Incident.severity == severity)
    pagination = query.order_by(Incident.created_at.desc()).paginate(
        page=page, per_page=current_app.config["ITEMS_PER_PAGE"], error_out=False
    )
    counts = {s: Incident.query.filter_by(status=s).count() for s in INCIDENT_STATUSES}
    return render_template(
        "incidents/list.html",
        pagination=pagination,
        counts=counts,
        filters={"status": status, "severity": severity},
    )


@incidents_bp.route("/<int:incident_id>")
@login_required
def detail(incident_id: int):
    return render_template("incidents/detail.html", incident=_get_incident(incident_id))


@incidents_bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    errors: dict[str, str] = {}
    if request.method == "POST":
        try:
            data = validate_incident_form(request.form)
            _check_references(data, errors)
            if not errors:
                incident = Incident(**data)
                if incident.status == "resolved":
                    incident.resolved_at = utcnow()
                db.session.add(incident)
                db.session.commit()
                flash("Incident created.", "success")
                return redirect(url_for("incidents.detail", incident_id=incident.id))
        except ValidationError as exc:
            errors = exc.errors
        return render_template(
            "incidents/form.html", errors=errors, form=request.form, incident=None, **_form_context()
        ), 400

    prefill = {
        "service_id": request.args.get("service_id", ""),
        "deployment_id": request.args.get("deployment_id", ""),
    }
    return render_template(
        "incidents/form.html", errors=errors, form=prefill, incident=None, **_form_context()
    )


@incidents_bp.route("/<int:incident_id>/edit", methods=["GET", "POST"])
@login_required
def edit(incident_id: int):
    incident = _get_incident(incident_id)
    errors: dict[str, str] = {}
    if request.method == "POST":
        try:
            data = validate_incident_form(request.form)
            _check_references(data, errors)
            if not errors:
                _apply_status_change(incident, data["status"])
                for key, value in data.items():
                    setattr(incident, key, value)
                db.session.commit()
                flash("Incident updated.", "success")
                return redirect(url_for("incidents.detail", incident_id=incident.id))
        except ValidationError as exc:
            errors = exc.errors
        return render_template(
            "incidents/form.html", errors=errors, form=request.form, incident=incident, **_form_context()
        ), 400
    return render_template(
        "incidents/form.html", errors=errors, form=incident.__dict__, incident=incident, **_form_context()
    )


@incidents_bp.route("/<int:incident_id>/resolve", methods=["POST"])
@login_required
def resolve(incident_id: int):
    incident = _get_incident(incident_id)
    _apply_status_change(incident, "resolved")
    incident.status = "resolved"
    db.session.commit()
    flash("Incident marked as resolved.", "success")
    return redirect(request.referrer or url_for("incidents.detail", incident_id=incident.id))


@incidents_bp.route("/<int:incident_id>/delete", methods=["POST"])
@login_required
def delete(incident_id: int):
    incident = _get_incident(incident_id)
    db.session.delete(incident)
    db.session.commit()
    flash("Incident deleted.", "info")
    return redirect(url_for("incidents.list_incidents"))
