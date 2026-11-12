"""Input validation helpers shared by the HTML forms and the REST API."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import (
    DEPLOYMENT_STATUSES,
    ENVIRONMENTS,
    INCIDENT_SEVERITIES,
    INCIDENT_STATUSES,
    SERVICE_STATUSES,
)

SERVICE_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{1,99}$")
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,64}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
COMMIT_RE = re.compile(r"^[a-zA-Z0-9]{4,64}$")

DEPLOYMENT_REQUIRED = (
    "commit_id",
    "commit_author",
    "commit_message",
    "build_number",
    "image_tag",
    "deployment_status",
    "service_name",
)

# Friendly aliases Jenkins pipelines commonly send
STATUS_ALIASES = {
    "succeeded": "success",
    "successful": "success",
    "passed": "success",
    "failure": "failed",
    "fail": "failed",
    "error": "failed",
    "rollback": "rolled_back",
    "rolledback": "rolled_back",
    "rolled-back": "rolled_back",
    "running": "in_progress",
    "in-progress": "in_progress",
    "pending": "in_progress",
}


class ValidationError(ValueError):
    def __init__(self, errors: dict[str, str]):
        super().__init__("Validation failed")
        self.errors = errors


def _clean(value) -> str:
    return str(value).strip() if value is not None else ""


def is_valid_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_status(value: str) -> str:
    value = _clean(value).lower().replace(" ", "_")
    return STATUS_ALIASES.get(value, value)


def validate_deployment_payload(payload) -> dict:
    """Validate the JSON body sent to POST /api/deployments."""
    if not isinstance(payload, dict):
        raise ValidationError({"body": "Request body must be a JSON object."})

    errors: dict[str, str] = {}
    data: dict = {}

    for field in DEPLOYMENT_REQUIRED:
        if _clean(payload.get(field)) == "":
            errors[field] = "This field is required."

    commit_id = _clean(payload.get("commit_id"))
    if commit_id and not COMMIT_RE.match(commit_id):
        errors["commit_id"] = "Must be 4-64 alphanumeric characters (git SHA)."
    data["commit_id"] = commit_id

    data["commit_author"] = _clean(payload.get("commit_author"))[:120]
    data["commit_message"] = _clean(payload.get("commit_message"))[:5000]

    build_raw = payload.get("build_number")
    try:
        build_number = int(str(build_raw).strip())
        if build_number < 0:
            raise ValueError
        data["build_number"] = build_number
    except (TypeError, ValueError):
        if "build_number" not in errors:
            errors["build_number"] = "Must be a non-negative integer."

    image_tag = _clean(payload.get("image_tag"))
    if len(image_tag) > 255:
        errors["image_tag"] = "Must be at most 255 characters."
    data["image_tag"] = image_tag

    status = normalize_status(payload.get("deployment_status"))
    if status and status not in DEPLOYMENT_STATUSES:
        errors["deployment_status"] = f"Must be one of: {', '.join(DEPLOYMENT_STATUSES)}."
    data["status"] = status

    service_name = _clean(payload.get("service_name"))
    if service_name and not SERVICE_NAME_RE.match(service_name):
        errors["service_name"] = "Use 2-100 letters, digits, dots, dashes or underscores."
    data["service_name"] = service_name

    environment = _clean(payload.get("environment")).lower() or "production"
    if environment not in ENVIRONMENTS:
        errors["environment"] = f"Must be one of: {', '.join(ENVIRONMENTS)}."
    data["environment"] = environment

    duration = payload.get("duration_seconds")
    if duration not in (None, ""):
        try:
            data["duration_seconds"] = max(0, int(float(duration)))
        except (TypeError, ValueError):
            errors["duration_seconds"] = "Must be a number of seconds."
    else:
        data["duration_seconds"] = None

    data["triggered_by"] = _clean(payload.get("triggered_by"))[:64] or "jenkins"
    data["notes"] = _clean(payload.get("notes"))[:5000] or None

    if errors:
        raise ValidationError(errors)
    return data


def validate_service_form(form) -> dict:
    errors: dict[str, str] = {}
    data = {
        "name": _clean(form.get("name")),
        "description": _clean(form.get("description")) or None,
        "repository_url": _clean(form.get("repository_url")) or None,
        "health_check_url": _clean(form.get("health_check_url")) or None,
        "environment": _clean(form.get("environment")) or "production",
        "status": _clean(form.get("status")) or "active",
        "owner": _clean(form.get("owner")) or None,
    }
    if not SERVICE_NAME_RE.match(data["name"]):
        errors["name"] = "Use 2-100 letters, digits, dots, dashes or underscores."
    for key in ("repository_url", "health_check_url"):
        if data[key] and not is_valid_url(data[key]):
            errors[key] = "Enter a valid http(s) URL."
    if data["environment"] not in ENVIRONMENTS:
        errors["environment"] = "Invalid environment."
    if data["status"] not in SERVICE_STATUSES:
        errors["status"] = "Invalid status."
    if errors:
        raise ValidationError(errors)
    return data


def validate_incident_form(form) -> dict:
    errors: dict[str, str] = {}
    data = {
        "title": _clean(form.get("title")),
        "description": _clean(form.get("description")) or None,
        "severity": _clean(form.get("severity")) or "medium",
        "status": _clean(form.get("status")) or "open",
        "service_id": None,
        "deployment_id": None,
    }
    if not 3 <= len(data["title"]) <= 200:
        errors["title"] = "Title must be between 3 and 200 characters."
    if data["severity"] not in INCIDENT_SEVERITIES:
        errors["severity"] = "Invalid severity."
    if data["status"] not in INCIDENT_STATUSES:
        errors["status"] = "Invalid status."
    for key in ("service_id", "deployment_id"):
        raw = _clean(form.get(key))
        if raw:
            try:
                data[key] = int(raw)
            except ValueError:
                errors[key] = "Invalid selection."
    if errors:
        raise ValidationError(errors)
    return data


def validate_registration(form) -> dict:
    errors: dict[str, str] = {}
    username = _clean(form.get("username"))
    email = _clean(form.get("email")).lower()
    password = form.get("password") or ""
    confirm = form.get("confirm_password") or ""
    if not USERNAME_RE.match(username):
        errors["username"] = "3-64 characters: letters, digits, dot, dash or underscore."
    if not EMAIL_RE.match(email) or len(email) > 120:
        errors["email"] = "Enter a valid email address."
    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters."
    elif not (re.search(r"[A-Za-z]", password) and re.search(r"\d", password)):
        errors["password"] = "Password must contain letters and numbers."
    if password != confirm:
        errors["confirm_password"] = "Passwords do not match."
    if errors:
        raise ValidationError(errors)
    return {"username": username, "email": email, "password": password}
