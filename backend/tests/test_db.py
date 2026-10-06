"""Migrations, ingestion, validation, rollback and integrity."""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db import ingest as ingest_mod
from app.db import schema
from app.db.ingest import IngestValidationError, ingest, ingest_reason, sha256_file
from app.db.migrations import MIGRATIONS, current_version, run_migrations


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
