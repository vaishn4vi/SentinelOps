"""Database models for SentinelOps: users, services, deployments, incidents."""

from __future__ import annotations

from datetime import datetime, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


def utcnow() -> datetime:
    """Naive UTC timestamp (MySQL DATETIME has no timezone)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ----- Allowed values -------------------------------------------------------
DEPLOYMENT_STATUSES = ("success", "failed", "rolled_back", "in_progress")
ENVIRONMENTS = ("development", "staging", "production")
SERVICE_STATUSES = ("active", "inactive", "degraded")
INCIDENT_SEVERITIES = ("low", "medium", "high", "critical")
INCIDENT_STATUSES = ("open", "investigating", "resolved")


class TimestampMixin:
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    last_login_at = db.Column(db.DateTime)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.username}>"


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None


class Service(TimestampMixin, db.Model):
    __tablename__ = "services"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    repository_url = db.Column(db.String(255))
    health_check_url = db.Column(db.String(255))
    environment = db.Column(db.String(20), nullable=False, default="production")
    status = db.Column(db.String(20), nullable=False, default="active")
    owner = db.Column(db.String(100))
    last_health_status = db.Column(db.String(20))
    last_health_check_at = db.Column(db.DateTime)

    deployments = db.relationship(
        "Deployment",
        back_populates="service",
        cascade="all, delete-orphan",
        order_by="desc(Deployment.created_at)",
        lazy="dynamic",
    )
    incidents = db.relationship(
        "Incident",
        back_populates="service",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    @property
    def latest_deployment(self):
        return self.deployments.first()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "repository_url": self.repository_url,
            "health_check_url": self.health_check_url,
            "environment": self.environment,
            "status": self.status,
            "owner": self.owner,
            "created_at": _iso(self.created_at),
        }

    def __repr__(self) -> str:
        return f"<Service {self.name}>"


class Deployment(TimestampMixin, db.Model):
    __tablename__ = "deployments"

    id = db.Column(db.Integer, primary_key=True)
    service_id = db.Column(
        db.Integer, db.ForeignKey("services.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commit_id = db.Column(db.String(64), nullable=False, index=True)
    commit_author = db.Column(db.String(120), nullable=False)
    commit_message = db.Column(db.Text, nullable=False)
    build_number = db.Column(db.Integer, nullable=False)
    image_tag = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="in_progress", index=True)
    environment = db.Column(db.String(20), nullable=False, default="production")
    duration_seconds = db.Column(db.Integer)
    triggered_by = db.Column(db.String(64), nullable=False, default="jenkins")
    notes = db.Column(db.Text)

    service = db.relationship("Service", back_populates="deployments")
    incidents = db.relationship("Incident", back_populates="deployment", lazy="dynamic")

    @property
    def short_commit(self) -> str:
        return (self.commit_id or "")[:8]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "service_name": self.service.name if self.service else None,
            "commit_id": self.commit_id,
            "commit_author": self.commit_author,
            "commit_message": self.commit_message,
            "build_number": self.build_number,
            "image_tag": self.image_tag,
            "deployment_status": self.status,
            "environment": self.environment,
            "duration_seconds": self.duration_seconds,
            "triggered_by": self.triggered_by,
            "notes": self.notes,
            "created_at": _iso(self.created_at),
        }

    def __repr__(self) -> str:
        return f"<Deployment #{self.build_number} {self.status}>"


class Incident(TimestampMixin, db.Model):
    __tablename__ = "incidents"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    severity = db.Column(db.String(20), nullable=False, default="medium", index=True)
    status = db.Column(db.String(20), nullable=False, default="open", index=True)
    service_id = db.Column(
        db.Integer, db.ForeignKey("services.id", ondelete="CASCADE"), nullable=True, index=True
    )
    deployment_id = db.Column(
        db.Integer, db.ForeignKey("deployments.id", ondelete="SET NULL"), nullable=True
    )
    auto_generated = db.Column(db.Boolean, nullable=False, default=False)
    resolved_at = db.Column(db.DateTime)

    service = db.relationship("Service", back_populates="incidents")
    deployment = db.relationship("Deployment", back_populates="incidents")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "service_name": self.service.name if self.service else None,
            "deployment_id": self.deployment_id,
            "auto_generated": self.auto_generated,
            "created_at": _iso(self.created_at),
            "resolved_at": _iso(self.resolved_at),
        }

    def __repr__(self) -> str:
        return f"<Incident {self.title!r} {self.status}>"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None
