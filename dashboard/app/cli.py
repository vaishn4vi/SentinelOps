"""Custom ``flask`` CLI commands.

Usage (inside the container):
    flask create-admin --username admin --email admin@example.com
    flask seed-demo [--force]
    flask simulate-deployment --service demo-app --status failed
"""

from __future__ import annotations

import hashlib
import time

import click
from flask import Flask

from .deployments import record_deployment
from .extensions import db
from .models import User
from .seed import seed_demo_data
from .validators import ValidationError, validate_deployment_payload


def register_cli(app: Flask) -> None:
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--email", prompt=True)
    @click.password_option()
    def create_admin(username: str, email: str, password: str) -> None:
        """Create a dashboard user."""
        if User.query.filter((User.username == username) | (User.email == email)).first():
            raise click.ClickException("A user with that username or email already exists.")
        user = User(username=username, email=email.lower())
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.secho(f"User '{username}' created.", fg="green")

    @app.cli.command("seed-demo")
    @click.option("--force", is_flag=True, help="Seed even if services already exist.")
    def seed_demo(force: bool) -> None:
        """Load demo services, deployments and incidents."""
        if seed_demo_data(force=force, seed=int(time.time()) if force else 42):
            click.secho("Demo data loaded.", fg="green")
        else:
            click.echo("Data already present; use --force to add more.")

    @app.cli.command("simulate-deployment")
    @click.option("--service", "service_name", default="demo-app")
    @click.option(
        "--status",
        default="success",
        type=click.Choice(["success", "failed", "rolled_back", "in_progress"]),
    )
    @click.option("--build", "build_number", type=int, default=None)
    @click.option("--author", default="cli-user")
    @click.option("--message", default="Simulated deployment from the CLI")
    def simulate_deployment(service_name, status, build_number, author, message) -> None:
        """Record a deployment exactly as the REST API would."""
        build_number = build_number or int(time.time()) % 100000
        commit = hashlib.sha1(f"{service_name}{build_number}{time.time()}".encode()).hexdigest()
        try:
            data = validate_deployment_payload(
                {
                    "commit_id": commit,
                    "commit_author": author,
                    "commit_message": message,
                    "build_number": build_number,
                    "image_tag": f"sentinelops/{service_name}:{build_number}",
                    "deployment_status": status,
                    "service_name": service_name,
                    "triggered_by": "cli",
                }
            )
        except ValidationError as exc:
            raise click.ClickException(str(exc.errors)) from exc
        deployment, incident, _ = record_deployment(data)
        click.secho(f"Recorded deployment #{deployment.id} ({status}).", fg="green")
        if incident:
            click.secho(f"Incident #{incident.id} opened automatically.", fg="yellow")
