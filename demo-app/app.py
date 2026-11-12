"""SentinelOps Demo Application.

A tiny REST API that represents the workload being deployed by the
SentinelOps CI/CD pipeline. It exposes health and version endpoints and
can simulate a broken release through the ``BREAK`` environment variable.

Configuration is read from the environment *at request time* so the
failure mode can be toggled without rebuilding the image (and so tests can
switch it with ``monkeypatch``).
"""

from __future__ import annotations

import logging
import os
import platform
import socket
import time
from datetime import datetime, timezone

from flask import Flask, jsonify

TRUTHY = {"1", "true", "yes", "on"}
START_TIME = time.time()


def is_broken() -> bool:
    """Return True when the BREAK environment variable requests a failure."""
    return os.environ.get("BREAK", "false").strip().lower() in TRUTHY


def app_version() -> str:
    return os.environ.get("APP_VERSION", "1.0.0")


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.sort_keys = False

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s [demo-app] %(message)s",
    )

    @app.get("/")
    def index():
        if is_broken():
            app.logger.error("Request to / failed: BREAK mode is enabled")
            return jsonify(
                status="error",
                message="Service is in simulated failure mode (BREAK=true)",
            ), 500
        return jsonify(
            service="sentinelops-demo-app",
            message="Hello from the SentinelOps demo application",
            version=app_version(),
            endpoints=["/", "/health", "/version"],
        )

    @app.get("/health")
    def health():
        uptime = round(time.time() - START_TIME, 2)
        checked_at = datetime.now(timezone.utc).isoformat()
        if is_broken():
            app.logger.error("Health check failed: BREAK mode is enabled")
            return jsonify(
                status="unhealthy",
                reason="Simulated failure (BREAK=true)",
                version=app_version(),
                uptime_seconds=uptime,
                checked_at=checked_at,
            ), 500
        return jsonify(
            status="healthy",
            version=app_version(),
            uptime_seconds=uptime,
            checked_at=checked_at,
        )

    @app.get("/version")
    def version():
        return jsonify(
            version=app_version(),
            build_number=os.environ.get("BUILD_NUMBER", "local"),
            commit_id=os.environ.get("COMMIT_ID", "local"),
            hostname=socket.gethostname(),
            python_version=platform.python_version(),
        )

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(status="error", message="Resource not found"), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(status="error", message="Method not allowed"), 405

    @app.errorhandler(Exception)
    def unhandled(error):
        app.logger.exception("Unhandled error: %s", error)
        return jsonify(status="error", message="Internal server error"), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
