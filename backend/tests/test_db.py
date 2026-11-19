"""Migrations, ingestion, validation, rollback and integrity."""

from __future__ import annotations

import pandas as pd
import numpy as np
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db import ingest as ingest_mod
from app.db import schema
from app.db.ingest import IngestValidationError, ingest, ingest_reason, sha256_file
from app.db.migrations import MIGRATIONS, current_version, run_migrations
from app.db.training import (
    load_city_training_frame,
    load_demand_training_frame,
    load_influencer_training_frame,
)
from app.services.model_registry import active_model, promote_model, register_model
from app.services.forecast_store import create_forecast_run, evaluate_forecast_run, record_forecasts


def _count(engine, table) -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(table)).scalar_one()


def _latest_run(engine) -> int | None:
    with engine.connect() as conn:
        return conn.execute(select(func.max(schema.ingest_runs.c.id))).scalar_one()


def test_migrations_apply_once(fresh_engine):
    assert run_migrations(fresh_engine) == [v for v, _, _ in MIGRATIONS]
    assert run_migrations(fresh_engine) == []
    assert current_version(fresh_engine) == MIGRATIONS[-1][0]


def test_ingest_loads_every_source_row(fresh_engine):
    report = ingest(fresh_engine, trigger="test", backup=False)

    expected = {
        "demand_daily": len(pd.read_csv(settings.demand_predictions_path(), usecols=["sku_id"])),
        "inventory": len(pd.read_csv(settings.inventory_path())),
        "signals": len(pd.read_csv(settings.signals_path(), usecols=["sku_id"])),
        "influencer_sample": len(pd.read_csv(settings.influencer_sample_path(), usecols=["lift_6h"])),
    }
    for table, n in expected.items():
        assert report.row_counts[table] == n
        assert _count(fresh_engine, schema.metadata.tables[table]) == n
    assert _count(fresh_engine, schema.skus) == 30
    assert report.warnings == []


def test_dataset_meta_records_source_checksums(fresh_engine):
    ingest(fresh_engine, trigger="test", backup=False)
    with fresh_engine.connect() as conn:
        meta = {r.dataset: r for r in conn.execute(select(schema.dataset_meta))}
    assert meta["demand_predictions"].source_sha256 == sha256_file(settings.demand_predictions_path())
    assert meta["inventory"].source_sha256 == sha256_file(settings.inventory_path())
    assert ingest_reason(fresh_engine) is None


def test_dataset_load_history_preserves_each_ingest(fresh_engine):
    ingest(fresh_engine, trigger="first", backup=False)
    ingest(fresh_engine, trigger="second", backup=False)
    expected_datasets = len(ingest_mod.present_source_checksums())

    with fresh_engine.connect() as conn:
        loads = conn.execute(select(schema.dataset_loads)).all()

    assert len(loads) == expected_datasets * 2
    assert {row.ingest_run_id for row in loads} == {1, 2}
    assert {row.dataset for row in loads} >= {"demand_predictions", "inventory", "city_economic"}


def test_incremental_ingest_preserves_older_demand_rows(fresh_engine, monkeypatch):
    ingest(fresh_engine, trigger="first", backup=False)
    original = ingest_mod.read_sources()
    monthly = original.demand.tail(30).copy()
    monthly["date"] = pd.to_datetime(monthly["date"]) + pd.Timedelta(days=1_000)
    monthly["predicted_units"] = monthly.get("predicted_units", np.nan)

    monkeypatch.setattr(
        ingest_mod,
        "read_sources",
        lambda: ingest_mod.SourceBundle(
            demand=monthly,
            demand_dataset=original.demand_dataset,
            inventory=None,
            signals=None,
            influencer_sample=original.influencer_sample,
            influencer_metrics=original.influencer_metrics,
            city_economic=original.city_economic,
            paths=original.paths,
        ),
    )
    report = ingest(fresh_engine, trigger="monthly", backup=False, mode="incremental")

    assert report.run_id == 2
    with fresh_engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(schema.demand_daily)).scalar_one()
    assert count == len(original.demand) + len(monthly)


def test_database_training_loaders_return_validated_frames(fresh_engine):
    ingest(fresh_engine, trigger="training", backup=False)

    demand = load_demand_training_frame(fresh_engine)
    influencer = load_influencer_training_frame(fresh_engine)

    assert list(demand.columns) == [
        "sku_id",
        "date",
        "brand_id",
        "category",
        *schema.DEMAND_FEATURE_COLUMNS,
        "units_sold",
    ]
    assert not demand[["sku_id", "date"]].duplicated().any()
    assert list(influencer.columns) == [
        "ws_flag",
        *schema.INFLUENCER_TARGETS,
        *schema.INFLUENCER_DEMO_FEATURES,
    ]
    city = load_city_training_frame(fresh_engine)
    assert list(city.columns) == [
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
    assert not city[["date", "city", "category"]].duplicated().any()


def test_raw_demand_is_retained_per_ingest_run(fresh_engine):
    ingest(fresh_engine, trigger="raw-audit", backup=False)
    ingest(fresh_engine, trigger="raw-audit-repeat", backup=False)
    expected = len(pd.read_csv(settings.demand_predictions_path(), usecols=["sku_id"]))

    with fresh_engine.connect() as conn:
        raw_count = conn.execute(select(func.count()).select_from(schema.raw_demand_daily)).scalar_one()
        run_count = conn.execute(select(func.count()).select_from(schema.ingest_runs)).scalar_one()

    assert raw_count == 2 * expected
    assert run_count == 2


def test_model_registry_promotes_and_retires_versions(fresh_engine, tmp_path):
    run_migrations(fresh_engine)
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"candidate artifact")
    register_model(
        fresh_engine,
        model_version="demand-v1",
        model_family="demand",
        artifact_path=artifact,
        feature_schema_version="demand-features-v1",
        training_cutoff=pd.Timestamp("2026-10-31").date(),
        metrics={"wmape": 0.12},
    )
    promote_model(fresh_engine, "demand-v1")

    artifact.write_bytes(b"better candidate artifact")
    register_model(
        fresh_engine,
        model_version="demand-v2",
        model_family="demand",
        artifact_path=artifact,
        feature_schema_version="demand-features-v1",
        training_cutoff=pd.Timestamp("2026-11-30").date(),
        metrics={"wmape": 0.10},
    )
    promote_model(fresh_engine, "demand-v2")

    with fresh_engine.connect() as conn:
        statuses = {
            row.model_version: row.status
            for row in conn.execute(select(schema.model_versions))
        }
    assert statuses == {"demand-v1": "retired", "demand-v2": "production"}
    assert active_model(fresh_engine, "demand")["model_version"] == "demand-v2"


def test_forecast_runs_are_persisted_and_evaluated(fresh_engine, tmp_path):
    ingest(fresh_engine, trigger="forecast-test", backup=False)
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"forecast artifact")
    register_model(
        fresh_engine,
        model_version="demand-forecast-v1",
        model_family="demand",
        artifact_path=artifact,
        feature_schema_version="demand-features-v1",
        training_cutoff=pd.Timestamp("2024-12-31").date(),
        metrics={},
    )
    run_id = create_forecast_run(
        fresh_engine,
        model_version="demand-forecast-v1",
        forecast_date_from=pd.Timestamp("2024-12-01").date(),
        forecast_date_to=pd.Timestamp("2024-12-01").date(),
    )
    record_forecasts(
        fresh_engine,
        forecast_run_id=run_id,
        model_version="demand-forecast-v1",
        rows=[{"sku_id": "PB-BD-001", "forecast_date": pd.Timestamp("2024-12-01").date(), "p50": 10.0}],
    )

    metrics = evaluate_forecast_run(fresh_engine, run_id)
    assert metrics["n"] == 1
    assert metrics["mae"] is not None
    assert metrics["wmape"] is not None


def test_reingest_is_idempotent_and_backs_up(fresh_engine, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_backup_dir", str(tmp_path / "bk"))
    first = ingest(fresh_engine, trigger="test", backup=True)
    assert first.backup_path is None  # nothing worth backing up yet
    second = ingest(fresh_engine, trigger="test", backup=True)
    assert second.run_id == first.run_id + 1
    assert second.row_counts == first.row_counts
    assert second.backup_path and list((tmp_path / "bk").glob("optichain-*.sqlite3"))


def test_validation_failure_leaves_database_untouched(fresh_engine, monkeypatch):
    ingest(fresh_engine, trigger="test", backup=False)
    run_before = _latest_run(fresh_engine)
    inv_before = _count(fresh_engine, schema.inventory)

    real_read = ingest_mod.read_sources

    def bad_read():
        bundle = real_read()
        bundle.inventory = pd.concat([bundle.inventory, bundle.inventory.head(1)], ignore_index=True)
        return bundle

    monkeypatch.setattr(ingest_mod, "read_sources", bad_read)
    with pytest.raises(IngestValidationError, match="duplicate"):
        ingest(fresh_engine, trigger="test", backup=False)

    assert _latest_run(fresh_engine) == run_before
    assert _count(fresh_engine, schema.inventory) == inv_before


def test_unknown_sku_in_inventory_is_rejected(fresh_engine, monkeypatch):
    real_read = ingest_mod.read_sources

    def bad_read():
        bundle = real_read()
        extra = bundle.inventory.head(1).assign(sku_id="NOT-A-SKU")
        bundle.inventory = pd.concat([bundle.inventory, extra], ignore_index=True)
        return bundle

    monkeypatch.setattr(ingest_mod, "read_sources", bad_read)
    with pytest.raises(IngestValidationError, match="not present in demand"):
        ingest(fresh_engine, trigger="test", backup=False)


def test_failed_verification_rolls_back(fresh_engine, monkeypatch):
    ingest(fresh_engine, trigger="test", backup=False)
    run_before = _latest_run(fresh_engine)
    demand_before = _count(fresh_engine, schema.demand_daily)

    def broken_verify(conn, bundle):
        raise AssertionError("simulated mismatch")

    monkeypatch.setattr(ingest_mod, "verify_loaded", broken_verify)
    with pytest.raises(AssertionError, match="simulated mismatch"):
        ingest(fresh_engine, trigger="test", backup=False)

    assert _latest_run(fresh_engine) == run_before
    assert _count(fresh_engine, schema.demand_daily) == demand_before


def test_changed_source_triggers_refresh(fresh_engine, monkeypatch):
    ingest(fresh_engine, trigger="test", backup=False)
    monkeypatch.setattr(
        ingest_mod, "present_source_checksums", lambda: {**ingest_mod.loaded_checksums(fresh_engine), "inventory": "x"}
    )
    assert "inventory" in ingest_reason(fresh_engine)


def test_foreign_keys_are_enforced(fresh_engine):
    ingest(fresh_engine, trigger="test", backup=False)
    with pytest.raises(IntegrityError):
        with fresh_engine.begin() as conn:
            conn.execute(
                schema.inventory.insert().values(
                    seq=10_000, sku_id="NOT-A-SKU", warehouse_id="W9",
                    stock_on_hand=1.0, on_order=0.0, lead_time_days=1,
                )
            )


def test_stored_values_round_trip_exactly(fresh_engine):
    ingest(fresh_engine, trigger="test", backup=False)
    src = pd.read_csv(settings.demand_predictions_path(), parse_dates=["date"])
    row = src.iloc[1234]
    with fresh_engine.connect() as conn:
        db = conn.execute(
            select(schema.demand_daily).where(
                schema.demand_daily.c.sku_id == row["sku_id"],
                schema.demand_daily.c.date == row["date"].date(),
            )
        ).mappings().one()
    for col in [*schema.DEMAND_FEATURE_COLUMNS, "units_sold", "predicted_units"]:
        assert db[col] == row[col], col
