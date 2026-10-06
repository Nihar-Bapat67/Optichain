"""Versioned schema migrations.

Each migration runs once, in its own transaction, and is recorded in
`schema_migrations`. Never edit an applied migration: append a new one.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import Connection, Engine, inspect, select

from app.core.logging import get_logger
from app.db import schema

logger = get_logger(__name__)


def _m0001_initial(conn: Connection) -> None:
    tables = [t for t in schema.metadata.sorted_tables if t.name != "schema_migrations"]
    schema.metadata.create_all(conn, tables=tables, checkfirst=True)


MIGRATIONS: list[tuple[int, str, Callable[[Connection], None]]] = [
    (1, "initial serving schema", _m0001_initial),
]


def applied_versions(engine: Engine) -> set[int]:
    if not inspect(engine).has_table("schema_migrations"):
        return set()
    with engine.connect() as conn:
        return {row[0] for row in conn.execute(select(schema.schema_migrations.c.version))}


def run_migrations(engine: Engine) -> list[int]:
    schema.schema_migrations.create(engine, checkfirst=True)
    done = applied_versions(engine)
    newly: list[int] = []
    for version, name, fn in MIGRATIONS:
        if version in done:
            continue
        with engine.begin() as conn:
            fn(conn)
            conn.execute(
                schema.schema_migrations.insert().values(
                    version=version,
                    name=name,
                    applied_at=datetime.now(timezone.utc).isoformat(),
                )
            )
        logger.info("Applied migration %04d: %s", version, name)
        newly.append(version)
    return newly


def current_version(engine: Engine) -> int:
    versions = applied_versions(engine)
    return max(versions) if versions else 0
