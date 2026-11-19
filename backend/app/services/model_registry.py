"""Database-backed model artifact registration and promotion."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, select

from app.db import schema

VALID_STATUSES = {"candidate", "production", "retired", "rejected"}


def artifact_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def register_model(
    engine: Engine,
    *,
    model_version: str,
    model_family: str,
    artifact_path: Path,
    feature_schema_version: str,
    training_cutoff: date,
    metrics: dict[str, Any],
    status: str = "candidate",
) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"unsupported model status: {status}")
    if not artifact_path.is_file():
        raise FileNotFoundError(artifact_path)

    values = {
        "model_version": model_version,
        "model_family": model_family,
        "artifact_path": str(artifact_path),
        "artifact_sha256": artifact_sha256(artifact_path),
        "feature_schema_version": feature_schema_version,
        "training_cutoff": training_cutoff,
        "status": status,
        "metrics_json": json.dumps(metrics, sort_keys=True),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with engine.begin() as conn:
        conn.execute(schema.model_versions.insert().values(**values))


def promote_model(engine: Engine, model_version: str) -> None:
    with engine.begin() as conn:
        candidate = conn.execute(
            select(schema.model_versions.c.model_family, schema.model_versions.c.status)
            .where(schema.model_versions.c.model_version == model_version)
        ).first()
        if candidate is None:
            raise ValueError(f"unknown model version: {model_version}")
        if candidate.status != "candidate":
            raise ValueError(f"model {model_version} is not a candidate")

        conn.execute(
            schema.model_versions.update()
            .where(
                schema.model_versions.c.model_family == candidate.model_family,
                schema.model_versions.c.status == "production",
            )
            .values(status="retired")
        )
        conn.execute(
            schema.model_versions.update()
            .where(schema.model_versions.c.model_version == model_version)
            .values(status="production")
        )


def active_model(engine: Engine, model_family: str) -> dict[str, Any] | None:
    with engine.connect() as conn:
        row = conn.execute(
            select(schema.model_versions)
            .where(
                schema.model_versions.c.model_family == model_family,
                schema.model_versions.c.status == "production",
            )
            .order_by(schema.model_versions.c.created_at.desc())
        ).mappings().first()
    return dict(row) if row else None
