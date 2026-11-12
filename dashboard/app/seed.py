"""Bootstrap data: optional admin account and realistic demo data."""

from __future__ import annotations

import hashlib
import os
import random
from datetime import timedelta

from flask import current_app

from .extensions import db
from .models import Deployment, Incident, Service, User, utcnow

DEMO_SERVICES = [
    {
        "name": "demo-app",
        "description": "SentinelOps demo REST API (health, version, failure simulation).",
        "repository_url": "https://github.com/example/sentinelops-demo-app",
        "environment": "production",
        "owner": "platform-team",
    },
    {
        "name": "payments-api",
        "description": "Payment processing microservice.",
        "repository_url": "https://github.com/example/payments-api",
        "environment": "production",
        "owner": "payments-team",
    },
    {
        "name": "auth-service",
        "description": "Authentication and token issuance.",
        "repository_url": "https://github.com/example/auth-service",
        "environment": "staging",
        "owner": "identity-team",
    },
    {
        "name": "notification-worker",
        "description": "Email / SMS notification background worker.",
        "repository_url": "https://github.com/example/notification-worker",
        "environment": "production",
        "owner": "platform-team",
    },
]

AUTHORS = ["Priya Sharma", "Arjun Mehta", "Sara Khan", "Rahul Verma", "Emily Chen"]
MESSAGES = [
    "feat: add pagination to listing endpoint",
    "fix: handle null values in payload parser",
    "chore: bump base image to python 3.12-slim",
    "perf: cache configuration lookups",
    "refactor: split service layer from routes",
    "fix: correct timeout on upstream calls",
    "feat: expose /version metadata",
    "ci: add unit tests to pipeline",
]


def ensure_admin() -> User | None:
    username = os.environ.get("ADMIN_USERNAME", "").strip()
    password = os.environ.get("ADMIN_PASSWORD", "")
    email = os.environ.get("ADMIN_EMAIL", "").strip() or f"{username}@sentinelops.local"
    if not username or not password:
        return None
    user = User.query.filter_by(username=username).first()
    if user:
        return user
    user = User(username=username, email=email.lower())
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    current_app.logger.info("Bootstrap admin user '%s' created", username)
    return user


def seed_demo_data(force: bool = False, seed: int = 42) -> bool:
    """Insert demo services, ~60 deployments and incidents. Idempotent unless force=True."""
    if Service.query.count() and not force:
        return False

    rng = random.Random(seed)
    now = utcnow()
    health_url = current_app.config.get("DEMO_APP_HEALTH_URL")

    services = []
    for spec in DEMO_SERVICES:
        service = Service.query.filter_by(name=spec["name"]).first()
        if not service:
            service = Service(status="active", **spec)
            if spec["name"] == "demo-app":
                service.health_check_url = health_url
            db.session.add(service)
        services.append(service)
    db.session.flush()

    build = {s.name: 100 for s in services}
    for day in range(13, -1, -1):
        for _ in range(rng.randint(2, 6)):
            service = rng.choice(services)
            build[service.name] += 1
            status = rng.choices(
                ["success", "failed", "rolled_back"], weights=[78, 14, 8]
            )[0]
            created = now - timedelta(days=day, hours=rng.randint(0, 20), minutes=rng.randint(0, 59))
            commit = hashlib.sha1(f"{service.name}-{build[service.name]}".encode()).hexdigest()
            deployment = Deployment(
                service=service,
                commit_id=commit,
                commit_author=rng.choice(AUTHORS),
                commit_message=rng.choice(MESSAGES),
                build_number=build[service.name],
                image_tag=f"sentinelops/{service.name}:{build[service.name]}-{commit[:7]}",
                status=status,
                environment=service.environment,
                duration_seconds=rng.randint(45, 420),
                triggered_by="jenkins",
                created_at=created,
                updated_at=created,
            )
            db.session.add(deployment)
            if status != "success" and rng.random() < 0.6:
                db.session.add(
                    Incident(
                        title=f"Deployment #{deployment.build_number} of {service.name} "
                        f"{'failed' if status == 'failed' else 'was rolled back'}",
                        description="Seeded demo incident.",
                        severity=rng.choice(["medium", "high", "critical"]),
                        status="resolved" if day > 2 else rng.choice(["open", "investigating"]),
                        service=service,
                        deployment=deployment,
                        auto_generated=True,
                        created_at=created,
                        updated_at=created,
                        resolved_at=created + timedelta(hours=2) if day > 2 else None,
                    )
                )
    db.session.commit()
    current_app.logger.info("Demo data seeded")
    return True
