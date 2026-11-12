import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("BREAK", "false")
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client
