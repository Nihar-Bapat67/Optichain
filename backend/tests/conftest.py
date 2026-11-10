"""Test fixtures.

Tests run against a throwaway SQLite database built from the real CSV sources,
so they never touch backend/var. Environment must be set before `app` is
imported, because settings are read at import time.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="optichain-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'api.sqlite3').as_posix()}"
os.environ["DATABASE_REQUIRE_POSTGRES"] = "false"
os.environ["DB_BACKUP_DIR"] = str(_TMP / "backups")
os.environ.setdefault("LOG_LEVEL", "WARNING")

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.engine import build_engine  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def fresh_engine(tmp_path):
    """An empty, isolated SQLite database for ingest tests."""
    engine = build_engine(f"sqlite:///{(tmp_path / 'ingest.sqlite3').as_posix()}")
    yield engine
    engine.dispose()


def pytest_sessionfinish(session, exitstatus):
    from app.db.engine import dispose_engine

    dispose_engine()
    shutil.rmtree(_TMP, ignore_errors=True)
