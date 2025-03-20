"""Shared pytest fixtures.

The database is created in a temporary directory *before* the application
modules are imported, because the SQLAlchemy engine is built at import time
from the settings.
"""

from __future__ import annotations

import os
import tempfile

_TMP = tempfile.mkdtemp(prefix="rqm-test-")
os.environ["RQM_DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["RQM_API_KEY"] = ""
os.environ["RQM_SCHEDULER_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _database():
    init_db()
    yield


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client
