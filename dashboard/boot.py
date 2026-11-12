"""Container entrypoint for the SentinelOps dashboard.

1. Waits until MySQL accepts connections (with retries).
2. Applies database migrations (flask db upgrade).
3. Creates the optional bootstrap admin and demo data.
4. Replaces itself with gunicorn.

Written in Python rather than shell so it is immune to Windows CRLF
line-ending problems when the repo is cloned on Windows.
"""

from __future__ import annotations

import logging
import os
import sys
import time

from sqlalchemy import create_engine, text

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [boot] %(message)s")
log = logging.getLogger("boot")


def wait_for_database(uri: str, attempts: int = 30, delay: float = 3.0) -> None:
    engine = create_engine(uri, pool_pre_ping=True)
    for attempt in range(1, attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("Database is reachable.")
            engine.dispose()
            return
        except Exception as exc:  # noqa: BLE001
            log.warning("Database not ready (attempt %s/%s): %s", attempt, attempts, exc.__class__.__name__)
            time.sleep(delay)
    engine.dispose()
    log.error("Database never became available; giving up.")
    sys.exit(1)


def main() -> None:
    from config import build_database_uri

    wait_for_database(build_database_uri())

    from flask_migrate import upgrade

    from app import create_app
    from app.seed import ensure_admin, seed_demo_data

    app = create_app()
    with app.app_context():
        log.info("Applying database migrations...")
        upgrade(directory=os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations"))
        ensure_admin()
        if os.environ.get("SEED_DEMO_DATA", "false").strip().lower() in {"1", "true", "yes", "on"}:
            if seed_demo_data():
                log.info("Demo data inserted.")
            else:
                log.info("Existing data found; demo seeding skipped.")

    workers = os.environ.get("GUNICORN_WORKERS", "2")
    args = [
        "gunicorn",
        "--bind", "0.0.0.0:5000",
        "--workers", workers,
        "--timeout", "60",
        "--access-logfile", "-",
        "--error-logfile", "-",
        "wsgi:app",
    ]
    log.info("Starting gunicorn with %s workers", workers)
    os.execvp(args[0], args)


if __name__ == "__main__":
    main()
