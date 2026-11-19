"""Training-frame loaders backed by the validated serving database."""

from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, select

from app.db import schema


def _frame(engine: Engine, table, columns: list[str]) -> pd.DataFrame:
    with engine.connect() as conn:
        result = conn.execute(select(*[table.c[column] for column in columns]))
        frame = pd.DataFrame(result.all(), columns=columns)
    if frame.empty:
        raise ValueError(f"database training table {table.name!r} is empty")
    return frame


def load_demand_training_frame(engine: Engine) -> pd.DataFrame:
    """Load the SKU/date demand training frame in deterministic order."""
    columns = [
        "sku_id",
        "date",
        "brand_id",
        "category",
        *schema.DEMAND_FEATURE_COLUMNS,
        "units_sold",
    ]
    frame = _frame(engine, schema.demand_daily, columns)
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    return frame.sort_values(["sku_id", "date"]).reset_index(drop=True)


def load_influencer_training_frame(engine: Engine) -> pd.DataFrame:
    """Load the validated influencer sample and target columns."""
    columns = [
        "ws_flag",
        *schema.INFLUENCER_TARGETS,
        *schema.INFLUENCER_DEMO_FEATURES,
    ]
    return _frame(engine, schema.influencer_sample, columns).sort_values("ws_flag").reset_index(drop=True)


def load_city_training_frame(engine: Engine) -> pd.DataFrame:
    """Load city/economic uplift rows with the original categorical columns."""
    columns = [
        "date",
        "city",
        "category",
        "day_of_year",
        "month",
        "median_income",
        "median_home_price",
        "affordability_ratio",
        "income_velocity_30d",
        "price_velocity_30d",
        "rolling_units_30d",
        "extra_units_sold",
    ]
    frame = _frame(engine, schema.city_economic_daily, columns)
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    return frame.sort_values(["date", "city", "category"]).reset_index(drop=True)
