"""Engine construction and connection pooling."""

from __future__ import annotations

import threading
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_engine: Engine | None = None
_lock = threading.Lock()


def _apply_sqlite_pragmas(dbapi_conn, _record) -> None:
    cur = dbapi_conn.cursor()
    # WAL lets readers proceed while an ingest transaction is writing.
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=30000")
    cur.execute("PRAGMA temp_store=MEMORY")
    cur.execute("PRAGMA cache_size=-32000")
    cur.close()


def build_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite":
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 30},
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
        )
        event.listen(engine, "connect", _apply_sqlite_pragmas)
    else:
        engine = create_engine(
            url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
    logger.info("Database engine ready: %s", parsed.render_as_string(hide_password=True))
    return engine


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        with _lock:
            if _engine is None:
                _engine = build_engine(settings.resolved_database_url())
    return _engine


def dispose_engine() -> None:
    global _engine
    with _lock:
        if _engine is not None:
            _engine.dispose()
            _engine = None


def is_sqlite(engine: Engine) -> bool:
    return engine.dialect.name == "sqlite"
