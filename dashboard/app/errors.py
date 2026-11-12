"""Error handlers: JSON for /api/*, HTML pages for everything else."""

from __future__ import annotations

from flask import Flask, jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from .extensions import db


def _wants_json() -> bool:
    return request.path.startswith("/api/")


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(CSRFError)
    def handle_csrf(error):
        if _wants_json():
            return jsonify(error="csrf_failed", message=error.description), 400
        return render_template(
            "errors/error.html",
            code=400,
            title="Session expired",
            message="Your form session expired. Please go back and try again.",
        ), 400

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(error):
        db.session.rollback()
        app.logger.exception("Database error: %s", error)
        if _wants_json():
            return jsonify(error="database_error", message="A database error occurred."), 500
        return render_template(
            "errors/error.html",
            code=500,
            title="Database error",
            message="SentinelOps could not complete the database operation. Please retry.",
        ), 500

    @app.errorhandler(HTTPException)
    def handle_http(error: HTTPException):
        if _wants_json():
            return jsonify(error=error.name.lower().replace(" ", "_"), message=error.description), error.code
        return render_template(
            "errors/error.html", code=error.code, title=error.name, message=error.description
        ), error.code

    @app.errorhandler(Exception)
    def handle_unexpected(error):
        db.session.rollback()
        app.logger.exception("Unhandled exception: %s", error)
        if _wants_json():
            return jsonify(error="internal_server_error", message="Unexpected server error."), 500
        return render_template(
            "errors/error.html",
            code=500,
            title="Internal server error",
            message="Something went wrong. The error has been logged.",
        ), 500
