"""Relational schema for the serving database.

Column lists mirror the CSV sources exactly. `seq` columns record the source
row order: several endpoints depend on CSV order (inventory iteration order
decides risk-register ties; signal rows are sorted with a non-stable sort),
so preserving it keeps responses byte-identical to the file-based version.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

metadata = MetaData()

# MODEL1 feature columns, in training order (== ws_model/feature_cols.pkl).
DEMAND_FEATURE_COLUMNS: list[str] = [
    "lag_7", "lag_30", "lag_365", "rolling_7", "rolling_30", "trend_ratio_7_30",
    "month", "day_of_week", "week_of_year", "quarter", "is_weekend", "is_q4", "day_of_month",
    "thanksgiving_pre_decay", "thanksgiving_post_decay",
    "blackfriday_pre_decay", "blackfriday_post_decay",
    "cybermonday_pre_decay", "cybermonday_post_decay",
    "christmas_pre_decay", "christmas_post_decay",
    "newyear_pre_decay", "newyear_post_decay",
    "mothersday_pre_decay", "mothersday_post_decay",
    "valentines_pre_decay", "valentines_post_decay",
    "superbowl_pre_decay", "superbowl_post_decay",
    "weddingseason_pre_decay", "weddingseason_post_decay",
    "backtocollege_pre_decay", "backtocollege_post_decay",
    "laborday_pre_decay", "laborday_post_decay",
    "days_to_thanksgiving", "days_to_christmas", "days_to_blackfriday", "days_to_mothersday",
    "bfcm_overlap", "holiday_pipeline", "spring_gifting",
    "ltv_tier_enc", "channel_enc", "is_gift_buyer", "is_registry_buyer",
    "conversion_rate", "active_registries", "items_fulfilled_this_month",
    "brand_enc", "category_enc",
]

DEMAND_INT_COLUMNS = {
    "month", "day_of_week", "week_of_year", "quarter", "is_weekend", "is_q4", "day_of_month",
    "days_to_thanksgiving", "days_to_christmas", "days_to_blackfriday", "days_to_mothersday",
    "ltv_tier_enc", "channel_enc", "brand_enc", "category_enc",
}
DEMAND_BOOL_COLUMNS = {"is_gift_buyer", "is_registry_buyer"}


def _feature_type(name: str):
    if name in DEMAND_BOOL_COLUMNS:
        return Boolean()
    if name in DEMAND_INT_COLUMNS:
        return Integer()
    return Float()


INFLUENCER_TARGETS = [
    "lift_6h", "lift_24h", "lift_48h", "lift_72h", "lift_96h", "peak_lift_pct", "decay_lambda",
]
INFLUENCER_DEMO_FEATURES = [f"demo_feat_{i}" for i in range(18)]


schema_migrations = Table(
    "schema_migrations",
    metadata,
    Column("version", Integer, primary_key=True),
    Column("name", String(200), nullable=False),
    Column("applied_at", String(40), nullable=False),
)

ingest_runs = Table(
    "ingest_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("started_at", String(40), nullable=False),
    Column("finished_at", String(40), nullable=False),
    Column("trigger", String(40), nullable=False),
    Column("notes", Text, nullable=False, default=""),
)

dataset_meta = Table(
    "dataset_meta",
    metadata,
    Column("dataset", String(64), primary_key=True),
    Column("source_path", Text, nullable=False),
    Column("source_sha256", String(64), nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("ingest_run_id", Integer, ForeignKey("ingest_runs.id"), nullable=False),
)

dataset_loads = Table(
    "dataset_loads",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ingest_run_id", Integer, ForeignKey("ingest_runs.id"), nullable=False),
    Column("dataset", String(64), nullable=False),
    Column("source_path", Text, nullable=False),
    Column("source_sha256", String(64), nullable=False),
    Column("row_count", Integer, nullable=False),
)

raw_demand_daily = Table(
    "raw_demand_daily",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ingest_run_id", Integer, ForeignKey("ingest_runs.id"), nullable=False),
    Column("sku_id", String(64), nullable=False),
    Column("date", Date, nullable=False),
    Column("brand_id", String(16), nullable=False),
    Column("category", String(64), nullable=False),
    Column("units_sold", Integer, nullable=False),
    UniqueConstraint("ingest_run_id", "sku_id", "date", name="uq_raw_demand_batch_sku_date"),
    Index("ix_raw_demand_sku_date", "sku_id", "date"),
)

skus = Table(
    "skus",
    metadata,
    Column("sku_id", String(64), primary_key=True),
    Column("brand_id", String(16), nullable=False),
    Column("category", String(64), nullable=False),
    Column("brand_enc", Integer, nullable=False),
    Column("category_enc", Integer, nullable=False),
)

demand_daily = Table(
    "demand_daily",
    metadata,
    Column("sku_id", String(64), ForeignKey("skus.sku_id"), primary_key=True),
    Column("date", Date, primary_key=True),
    Column("brand_id", String(16), nullable=False),
    Column("category", String(64), nullable=False),
    *[Column(name, _feature_type(name), nullable=False) for name in DEMAND_FEATURE_COLUMNS],
    Column("units_sold", Integer, nullable=False),
    # NULL when the table was built from ml_ready data (no MODEL1 predictions).
    Column("predicted_units", Float, nullable=True),
    Index("ix_demand_daily_date", "date"),
)

inventory = Table(
    "inventory",
    metadata,
    Column("seq", Integer, nullable=False, unique=True),
    Column("sku_id", String(64), ForeignKey("skus.sku_id"), primary_key=True),
    Column("warehouse_id", String(32), primary_key=True),
    Column("stock_on_hand", Float, nullable=False),
    Column("on_order", Float, nullable=False),
    Column("lead_time_days", Integer, nullable=False),
)

signals = Table(
    "signals",
    metadata,
    Column("seq", Integer, primary_key=True, autoincrement=False),
    Column("date", Date, nullable=False),
    Column("sku_id", String(64), ForeignKey("skus.sku_id"), nullable=False),
    Column("signal_type", String(32), nullable=False),
    Column("volume", Float, nullable=False),
    Column("source", String(64), nullable=False),
    UniqueConstraint("sku_id", "date", "signal_type", name="uq_signals_sku_date_type"),
    Index("ix_signals_sku_seq", "sku_id", "seq"),
    Index("ix_signals_date", "date"),
)

influencer_sample = Table(
    "influencer_sample",
    metadata,
    Column("seq", Integer, primary_key=True, autoincrement=False),
    Column("ws_flag", Integer, nullable=False),
    *[Column(name, Float, nullable=False) for name in INFLUENCER_TARGETS],
    *[Column(name, Float, nullable=False) for name in INFLUENCER_DEMO_FEATURES],
    Column("peak_lift_pct_pred", Float, nullable=True),
)

documents = Table(
    "documents",
    metadata,
    Column("key", String(64), primary_key=True),
    Column("body", Text, nullable=False),
)

city_economic_daily = Table(
    "city_economic_daily",
    metadata,
    Column("city", String(64), primary_key=True),
    Column("category", String(64), primary_key=True),
    Column("date", Date, primary_key=True),
    Column("day_of_year", Integer, nullable=False),
    Column("month", Integer, nullable=False),
    Column("median_income", Float, nullable=False),
    Column("median_home_price", Float, nullable=False),
    Column("affordability_ratio", Float, nullable=False),
    Column("income_velocity_30d", Float, nullable=False),
    Column("price_velocity_30d", Float, nullable=False),
    Column("rolling_units_30d", Float, nullable=False),
    Column("extra_units_sold", Float, nullable=False),
    Index("ix_city_economic_date", "date"),
)

model_versions = Table(
    "model_versions",
    metadata,
    Column("model_version", String(128), primary_key=True),
    Column("model_family", String(64), nullable=False),
    Column("artifact_path", Text, nullable=False),
    Column("artifact_sha256", String(64), nullable=False),
    Column("feature_schema_version", String(64), nullable=False),
    Column("training_cutoff", Date, nullable=False),
    Column("status", String(32), nullable=False),
    Column("metrics_json", Text, nullable=False),
    Column("created_at", String(40), nullable=False),
)

training_runs = Table(
    "training_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("model_family", String(64), nullable=False),
    Column("source_ingest_run_id", Integer, ForeignKey("ingest_runs.id"), nullable=True),
    Column("candidate_version", String(128), nullable=True),
    Column("started_at", String(40), nullable=False),
    Column("finished_at", String(40), nullable=True),
    Column("status", String(32), nullable=False),
    Column("metrics_json", Text, nullable=False, default="{}"),
)

forecast_runs = Table(
    "forecast_runs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("model_version", String(128), ForeignKey("model_versions.model_version"), nullable=False),
    Column("generated_at", String(40), nullable=False),
    Column("forecast_date_from", Date, nullable=False),
    Column("forecast_date_to", Date, nullable=False),
    Column("status", String(32), nullable=False),
)

forecasts = Table(
    "forecasts",
    metadata,
    Column("forecast_run_id", Integer, ForeignKey("forecast_runs.id"), primary_key=True),
    Column("model_version", String(128), ForeignKey("model_versions.model_version"), primary_key=True),
    Column("sku_id", String(64), ForeignKey("skus.sku_id"), primary_key=True),
    Column("forecast_date", Date, primary_key=True),
    Column("p10", Float, nullable=True),
    Column("p50", Float, nullable=False),
    Column("p90", Float, nullable=True),
    Column("generated_at", String(40), nullable=False),
)

# Tables the ingest job owns and fully replaces, in dependency order.
DATA_TABLES = [
    skus,
    demand_daily,
    inventory,
    signals,
    influencer_sample,
    documents,
    city_economic_daily,
]
