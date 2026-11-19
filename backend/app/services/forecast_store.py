"""Persistence and delayed evaluation for versioned forecasts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import Engine, select

from app.db import schema


def create_forecast_run(
    engine: Engine,
    *,
    model_version: str,
    forecast_date_from: date,
    forecast_date_to: date,
) -> int:
    if forecast_date_to < forecast_date_from:
        raise ValueError("forecast_date_to must not precede forecast_date_from")
    with engine.begin() as conn:
        run_id = conn.execute(
            schema.forecast_runs.insert().values(
                model_version=model_version,
                generated_at=datetime.now(timezone.utc).isoformat(),
                forecast_date_from=forecast_date_from,
                forecast_date_to=forecast_date_to,
                status="created",
            )
        ).inserted_primary_key[0]
    return int(run_id)


def record_forecasts(
    engine: Engine,
    *,
    forecast_run_id: int,
    model_version: str,
    rows: list[dict[str, Any]],
) -> None:
    if not rows:
        raise ValueError("at least one forecast row is required")
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = []
    for row in rows:
        if "sku_id" not in row or "forecast_date" not in row or "p50" not in row:
            raise ValueError("forecast rows require sku_id, forecast_date, and p50")
        payload.append(
            {
                "forecast_run_id": forecast_run_id,
                "model_version": model_version,
                "sku_id": row["sku_id"],
                "forecast_date": row["forecast_date"],
                "p10": row.get("p10"),
                "p50": float(row["p50"]),
                "p90": row.get("p90"),
                "generated_at": generated_at,
            }
        )
    with engine.begin() as conn:
        conn.execute(
            schema.forecast_runs.update()
            .where(schema.forecast_runs.c.id == forecast_run_id)
            .values(status="published")
        )
        conn.execute(schema.forecasts.insert(), payload)


def evaluate_forecast_run(engine: Engine, forecast_run_id: int) -> dict[str, float | int | None]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(
                schema.forecasts.c.p50,
                schema.demand_daily.c.units_sold,
            )
            .select_from(
                schema.forecasts.join(
                    schema.demand_daily,
                    (schema.forecasts.c.sku_id == schema.demand_daily.c.sku_id)
                    & (schema.forecasts.c.forecast_date == schema.demand_daily.c.date),
                )
            )
            .where(schema.forecasts.c.forecast_run_id == forecast_run_id)
        ).all()
    if not rows:
        return {"n": 0, "mae": None, "bias": None, "wmape": None}

    frame = pd.DataFrame(rows, columns=["prediction", "actual"])
    error = frame["prediction"].to_numpy(dtype=float) - frame["actual"].to_numpy(dtype=float)
    actual = frame["actual"].to_numpy(dtype=float)
    denominator = float(np.abs(actual).sum())
    return {
        "n": int(len(frame)),
        "mae": float(np.abs(error).mean()),
        "bias": float(error.mean()),
        "wmape": float(np.abs(error).sum() / denominator) if denominator else None,
    }
