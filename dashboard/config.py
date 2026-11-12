"""Configuration classes for the SentinelOps dashboard.

All secrets and connection settings come from environment variables.
Nothing sensitive is hard-coded here.
"""

from __future__ import annotations

import os
from urllib.parse import quote_plus


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def build_database_uri() -> str:
    """Build the SQLAlchemy URI from DATABASE_URL or the individual DB_* variables."""
    explicit = os.environ.get("DATABASE_URL")
    if explicit:
        return explicit

    host = os.environ.get("DB_HOST", "localhost")
    port = os.environ.get("DB_PORT", "3306")
    name = os.environ.get("DB_NAME", "sentinelops")
    user = os.environ.get("DB_USER", "")
    password = os.environ.get("DB_PASSWORD", "")
    if not user:
        raise RuntimeError(
            "Database is not configured. Set DATABASE_URL or DB_HOST/DB_USER/DB_PASSWORD/DB_NAME."
        )
    return (
        f"mysql+pymysql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{name}?charset=utf8mb4"
    )


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    SENTINELOPS_API_KEY = os.environ.get("SENTINELOPS_API_KEY", "")
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
    DEMO_APP_HEALTH_URL = os.environ.get("DEMO_APP_HEALTH_URL", "http://demo-app:8080/health")
    HEALTH_CHECK_TIMEOUT = float(os.environ.get("HEALTH_CHECK_TIMEOUT", "5"))
    ITEMS_PER_PAGE = int(os.environ.get("ITEMS_PER_PAGE", "15"))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    WTF_CSRF_TIME_LIMIT = None

    @classmethod
    def database_uri(cls) -> str:
        return build_database_uri()


class ProductionConfig(BaseConfig):
    DEBUG = False


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SENTINELOPS_API_KEY = "test-api-key"
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS: dict = {}

    @classmethod
    def database_uri(cls) -> str:
        return os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")


CONFIGS = {
    "production": ProductionConfig,
    "development": DevelopmentConfig,
    "testing": TestingConfig,
}


def get_config(name: str | None = None):
    name = (name or os.environ.get("FLASK_ENV", "production")).lower()
    return CONFIGS.get(name, ProductionConfig)
