"""Blueprint registration."""

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from ..extensions import csrf
    from .api import api_bp
    from .auth import auth_bp
    from .incidents import incidents_bp
    from .main import main_bp
    from .services import services_bp

    # The REST API is authenticated with an API key, not session cookies,
    # so it is exempt from CSRF protection.
    csrf.exempt(api_bp)

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(services_bp)
    app.register_blueprint(incidents_bp)
    app.register_blueprint(api_bp)
