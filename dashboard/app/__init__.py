"""SentinelOps dashboard application factory."""

from __future__ import annotations

import logging

from flask import Flask

from config import get_config

from .extensions import csrf, db, login_manager, migrate


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)
    config = get_config(config_name)
    app.config.from_object(config)
    app.config["SQLALCHEMY_DATABASE_URI"] = config.database_uri()

    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable is required.")

    logging.basicConfig(
        level=app.config.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s [dashboard] %(name)s: %(message)s",
    )
    app.logger.setLevel(app.config.get("LOG_LEVEL", "INFO"))

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import models  # noqa: F401  (register models with SQLAlchemy / Alembic)
    from .cli import register_cli
    from .errors import register_error_handlers
    from .routes import register_blueprints
    from .template_helpers import register_template_helpers

    register_blueprints(app)
    register_error_handlers(app)
    register_template_helpers(app)
    register_cli(app)

    return app
