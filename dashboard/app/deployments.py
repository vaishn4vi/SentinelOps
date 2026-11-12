"""Domain logic for recording deployments.

Kept separate from the HTTP layer so it can be reused by the API, CLI
commands and tests.
"""

from __future__ import annotations

from .extensions import db
from .models import Deployment, Incident, Service

FAILURE_STATUSES = {"failed", "rolled_back"}


def get_or_create_service(name: str, environment: str = "production") -> tuple[Service, bool]:
    service = Service.query.filter_by(name=name).first()
    if service:
        return service, False
    service = Service(
        name=name,
        environment=environment,
        status="active",
        description="Auto-registered from the CI/CD pipeline.",
    )
    db.session.add(service)
    db.session.flush()
    return service, True


def record_deployment(data: dict) -> tuple[Deployment, Incident | None, bool]:
    """Persist a validated deployment.

    Failed or rolled-back deployments automatically open an incident and
    mark the service as degraded; a later successful deployment marks the
    service active again (self-healing signal).

    Returns ``(deployment, incident_or_None, service_created)``.
    """
    service, created = get_or_create_service(data["service_name"], data["environment"])

    deployment = Deployment(
        service=service,
        commit_id=data["commit_id"],
        commit_author=data["commit_author"],
        commit_message=data["commit_message"],
        build_number=data["build_number"],
        image_tag=data["image_tag"],
        status=data["status"],
        environment=data["environment"],
        duration_seconds=data.get("duration_seconds"),
        triggered_by=data.get("triggered_by") or "jenkins",
        notes=data.get("notes"),
    )
    db.session.add(deployment)
    db.session.flush()

    incident = None
    if deployment.status in FAILURE_STATUSES:
        service.status = "degraded"
        verb = "failed" if deployment.status == "failed" else "was rolled back"
        incident = Incident(
            title=f"Deployment #{deployment.build_number} of {service.name} {verb}",
            description=(
                f"Automatic incident created by SentinelOps.\n"
                f"Commit: {deployment.commit_id} by {deployment.commit_author}\n"
                f"Message: {deployment.commit_message}\n"
                f"Image: {deployment.image_tag}"
            ),
            severity="high" if deployment.environment == "production" else "medium",
            status="open",
            service=service,
            deployment=deployment,
            auto_generated=True,
        )
        db.session.add(incident)
    elif deployment.status == "success" and service.status == "degraded":
        service.status = "active"

    db.session.commit()
    return deployment, incident, created
