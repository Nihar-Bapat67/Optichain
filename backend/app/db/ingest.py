"""CSV → database ingestion.

Run from backend/:  python -m app.db.ingest [--no-backup] [--force]

Safety properties:
* Source files are only read, never modified.
* Every source is validated before the database is touched.
* SQLite databases are backed up (online backup API) before being rewritten.
* All tables are replaced inside ONE transaction, and the written rows are read
  back and compared value-for-value against the sources before COMMIT. Any
  mismatch rolls the whole load back, leaving the previous data in place.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
from sqlalchemy import Connection, Engine, func, select

from app.config import settings
from app.core.logging import get_logger
from app.db import schema
from app.db.engine import is_sqlite
from app.db.migrations import run_migrations
from app.services import tables as csv_sources

logger = get_logger(__name__)


class IngestValidationError(ValueError):
    """Raised when a source file fails validation; nothing has been written."""


@dataclass
class SourceBundle:
    demand: pd.DataFrame
    demand_dataset: str  # "demand_predictions" or "ml_ready"
    inventory: pd.DataFrame | None
    signals: pd.DataFrame | None
    influencer_sample: pd.DataFrame | None
    influencer_metrics: dict | None
    city_economic: pd.DataFrame | None
    paths: dict[str, Path] = field(default_factory=dict)


@dataclass
class IngestReport:
    run_id: int
    trigger: str
    row_counts: dict[str, int]
    duration_s: float
    backup_path: str | None
    warnings: list[str]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def source_paths() -> dict[str, Path]:
    return {
        "demand_predictions": settings.demand_predictions_path(),
        "ml_ready": settings.ml_ready_path(),
        "inventory": settings.inventory_path(),
        "signals": settings.signals_path(),
        "influencer_sample": settings.influencer_sample_path(),
        "influencer_metrics": settings.influencer_metrics_path(),
        "city_economic": settings.city_economic_path(),
    }


def present_source_checksums() -> dict[str, str]:
    """Checksums of the sources an ingest would load right now."""
    paths = source_paths()
    out: dict[str, str] = {}
    demand_key = "demand_predictions" if paths["demand_predictions"].is_file() else "ml_ready"
    for key in (
        demand_key,
        "inventory",
        "signals",
        "influencer_sample",
        "influencer_metrics",
        "city_economic",
    ):
        if paths[key].is_file():
            out[key] = sha256_file(paths[key])
    return out


# ── Reading ─────────────────────────────────────────────────────────────────


def read_sources() -> SourceBundle:
    paths = source_paths()
    demand = csv_sources.load_demand_predictions()
    dataset = "demand_predictions"
    if demand is None:
        demand = csv_sources.load_sales_fallback()
        dataset = "ml_ready"
    if demand is None:
        raise IngestValidationError(
            f"No demand source found: neither {paths['demand_predictions']} nor {paths['ml_ready']} exists."
        )
    return SourceBundle(
        demand=demand,
        demand_dataset=dataset,
        inventory=csv_sources.load_inventory(),
        signals=csv_sources.load_signals(),
        influencer_sample=csv_sources.load_influencer_sample(),
        influencer_metrics=csv_sources.load_influencer_metrics(),
        city_economic=csv_sources.load_city_economic(),
        paths=paths,
    )


# ── Validation ──────────────────────────────────────────────────────────────


def _require_columns(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise IngestValidationError(f"{name}: missing required columns {missing}")


def _require_no_nulls(df: pd.DataFrame, cols: list[str], name: str) -> None:
    nulls = {c: int(n) for c, n in df[cols].isna().sum().items() if n}
    if nulls:
        raise IngestValidationError(f"{name}: null values in required columns {nulls}")


def _require_unique(df: pd.DataFrame, cols: list[str], name: str) -> None:
    dups = int(df.duplicated(cols).sum())
    if dups:
        raise IngestValidationError(f"{name}: {dups} duplicate rows on key {cols}")


def _coerce_int(df: pd.DataFrame, cols: list[str], name: str) -> None:
    for c in cols:
        if pd.api.types.is_integer_dtype(df[c]):
            continue
        values = pd.to_numeric(df[c], errors="raise")
        if not np.all(np.mod(values, 1) == 0):
            raise IngestValidationError(f"{name}.{c}: expected integers")
        df[c] = values.astype("int64")


def validate(bundle: SourceBundle) -> list[str]:
    """Raise IngestValidationError on hard failures; return soft warnings."""
    warnings: list[str] = []

    d = bundle.demand
    key_cols = ["date", "sku_id", "brand_id", "category"]
    _require_columns(d, key_cols + schema.DEMAND_FEATURE_COLUMNS + ["units_sold"], "demand")
    _require_no_nulls(d, key_cols + schema.DEMAND_FEATURE_COLUMNS + ["units_sold"], "demand")
    _require_unique(d, ["sku_id", "date"], "demand")
    _coerce_int(d, sorted(schema.DEMAND_INT_COLUMNS) + ["units_sold"], "demand")
    per_sku = d.groupby("sku_id")[["brand_id", "category", "brand_enc", "category_enc"]].nunique()
    inconsistent = per_sku[(per_sku > 1).any(axis=1)].index.tolist()
    if inconsistent:
        raise IngestValidationError(f"demand: SKUs with conflicting brand/category metadata: {inconsistent}")
    if (d["units_sold"] < 0).any():
        warnings.append(f"demand: {int((d['units_sold'] < 0).sum())} rows with negative units_sold")
    known_skus = set(d["sku_id"])

    if bundle.inventory is not None:
        inv = bundle.inventory
        cols = ["sku_id", "warehouse_id", "stock_on_hand", "on_order", "lead_time_days"]
        _require_columns(inv, cols, "inventory")
        _require_no_nulls(inv, cols, "inventory")
        _require_unique(inv, ["sku_id", "warehouse_id"], "inventory")
        _coerce_int(inv, ["lead_time_days"], "inventory")
        unknown = sorted(set(inv["sku_id"]) - known_skus)
        if unknown:
            raise IngestValidationError(f"inventory: SKUs not present in demand data: {unknown}")
        negative = int((inv[["stock_on_hand", "on_order", "lead_time_days"]] < 0).any(axis=1).sum())
        if negative:
            warnings.append(f"inventory: {negative} rows with negative stock, on-order or lead time")

    if bundle.signals is not None:
        s = bundle.signals
        cols = ["date", "sku_id", "signal_type", "volume", "source"]
        _require_columns(s, cols, "signals")
        _require_no_nulls(s, cols, "signals")
        _require_unique(s, ["sku_id", "date", "signal_type"], "signals")
        unknown = sorted(set(s["sku_id"]) - known_skus)
        if unknown:
            raise IngestValidationError(f"signals: SKUs not present in demand data: {unknown}")

    if bundle.influencer_sample is not None:
        x = bundle.influencer_sample
        cols = ["ws_flag", *schema.INFLUENCER_TARGETS, *schema.INFLUENCER_DEMO_FEATURES]
        _require_columns(x, cols, "influencer_sample")
        _require_no_nulls(x, cols, "influencer_sample")
        _coerce_int(x, ["ws_flag"], "influencer_sample")
        # The source CSV repeats the ws_flag header; pandas reads the copy as ws_flag.1.
        if "ws_flag.1" in x.columns and not (x["ws_flag"] == x["ws_flag.1"]).all():
            warnings.append("influencer_sample: duplicated ws_flag columns disagree; keeping the first")

    if bundle.city_economic is not None:
        city = bundle.city_economic
        city_cols = [
            "date", "city", "category", "day_of_year", "month", "median_income",
            "median_home_price", "affordability_ratio", "income_velocity_30d",
            "price_velocity_30d", "rolling_units_30d", "extra_units_sold",
        ]
        _require_columns(city, city_cols, "city_economic")
        _require_no_nulls(city, city_cols, "city_economic")
        _require_unique(city, ["date", "city", "category"], "city_economic")
        _coerce_int(city, ["day_of_year", "month"], "city_economic")
        if (city["extra_units_sold"] < 0).any():
            warnings.append(
                f"city_economic: {int((city['extra_units_sold'] < 0).sum())} negative target rows"
            )

    for w in warnings:
        logger.warning("Ingest validation: %s", w)
    return warnings


# ── Row building ────────────────────────────────────────────────────────────


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    # to_dict boxes numpy scalars into native Python types; NaN must become NULL.
    out = df.astype(object).where(df.notna(), None)
    return out.to_dict("records")


def build_rows(bundle: SourceBundle) -> dict[str, list[dict[str, Any]]]:
    d = bundle.demand
    sku_frame = (
        d[["sku_id", "brand_id", "category", "brand_enc", "category_enc"]]
        .drop_duplicates("sku_id")
        .sort_values("sku_id")
    )
    demand_cols = ["sku_id", "date", "brand_id", "category", *schema.DEMAND_FEATURE_COLUMNS, "units_sold"]
    dem = d[demand_cols].copy()
    dem["date"] = pd.to_datetime(dem["date"]).dt.date
    dem["predicted_units"] = d["predicted_units"] if "predicted_units" in d.columns else np.nan

    rows: dict[str, list[dict[str, Any]]] = {
        "skus": _records(sku_frame),
        "demand_daily": _records(dem),
        "inventory": [],
        "signals": [],
        "influencer_sample": [],
        "documents": [],
        "city_economic_daily": [],
    }

    if bundle.inventory is not None:
        inv = bundle.inventory[["sku_id", "warehouse_id", "stock_on_hand", "on_order", "lead_time_days"]].copy()
        inv.insert(0, "seq", np.arange(len(inv)))
        rows["inventory"] = _records(inv)

    if bundle.signals is not None:
        s = bundle.signals[["date", "sku_id", "signal_type", "volume", "source"]].copy()
        s["date"] = pd.to_datetime(s["date"]).dt.date
        s.insert(0, "seq", np.arange(len(s)))
        rows["signals"] = _records(s)

    if bundle.influencer_sample is not None:
        x = bundle.influencer_sample
        cols = ["ws_flag", *schema.INFLUENCER_TARGETS, *schema.INFLUENCER_DEMO_FEATURES]
        frame = x[cols].copy()
        frame["peak_lift_pct_pred"] = x["peak_lift_pct_pred"] if "peak_lift_pct_pred" in x.columns else np.nan
        frame.insert(0, "seq", np.arange(len(frame)))
        rows["influencer_sample"] = _records(frame)

    if bundle.influencer_metrics is not None:
        rows["documents"].append({"key": "influencer_metrics", "body": json.dumps(bundle.influencer_metrics)})

    if bundle.city_economic is not None:
        city_cols = [
            "city", "category", "date", "day_of_year", "month", "median_income",
            "median_home_price", "affordability_ratio", "income_velocity_30d",
            "price_velocity_30d", "rolling_units_30d", "extra_units_sold",
        ]
        city = bundle.city_economic[city_cols].copy()
        city["date"] = pd.to_datetime(city["date"]).dt.date
        rows["city_economic_daily"] = _records(city)

    return rows


# ── Verification (runs inside the load transaction, before COMMIT) ──────────


def _read_frame(conn: Connection, stmt) -> pd.DataFrame:
    result = conn.execute(stmt)
    return pd.DataFrame(result.all(), columns=list(result.keys()))


def verify_loaded(conn: Connection, bundle: SourceBundle) -> None:
    """Compare every loaded value with its source. Raises AssertionError on mismatch."""
    d = bundle.demand
    cols = ["sku_id", "date", *schema.DEMAND_FEATURE_COLUMNS, "units_sold"]
    src = d[cols].copy()
    src["date"] = pd.to_datetime(src["date"])
    src = src.sort_values(["sku_id", "date"]).reset_index(drop=True)
    db = _read_frame(conn, select(*[schema.demand_daily.c[c] for c in cols]).order_by("sku_id", "date"))
    db["date"] = pd.to_datetime(db["date"])
    for c in cols:
        db[c] = db[c].astype(src[c].dtype)
    float_cols = [c for c in cols if pd.api.types.is_float_dtype(src[c])]
    exact_cols = [c for c in cols if c not in float_cols]
    pd.testing.assert_frame_equal(db[exact_cols], src[exact_cols], check_exact=True)
    for c in float_cols:
        np.testing.assert_allclose(
            db[c].to_numpy(dtype=float),
            src[c].to_numpy(dtype=float),
            rtol=1e-12,
            atol=1e-12,
            err_msg=f"demand column {c} differs after database round-trip",
        )

    if "predicted_units" in d.columns:
        src_pred = d.assign(date=pd.to_datetime(d["date"])).sort_values(["sku_id", "date"])["predicted_units"]
        db_pred = _read_frame(
            conn, select(schema.demand_daily.c.predicted_units).order_by("sku_id", "date")
        )["predicted_units"].astype(float)
        np.testing.assert_allclose(
            db_pred.to_numpy(),
            src_pred.to_numpy(dtype=float),
            rtol=1e-12,
            atol=1e-12,
            err_msg="predicted_units differs after database round-trip",
        )

    if bundle.inventory is not None:
        inv_cols = ["sku_id", "warehouse_id", "stock_on_hand", "on_order", "lead_time_days"]
        db_inv = _read_frame(conn, select(*[schema.inventory.c[c] for c in inv_cols]).order_by("seq"))
        pd.testing.assert_frame_equal(
            db_inv.astype(bundle.inventory[inv_cols].dtypes.to_dict()),
            bundle.inventory[inv_cols].reset_index(drop=True),
            check_exact=True,
        )

    if bundle.signals is not None:
        sig_cols = ["date", "sku_id", "signal_type", "volume", "source"]
        db_sig = _read_frame(conn, select(*[schema.signals.c[c] for c in sig_cols]).order_by("seq"))
        db_sig["date"] = pd.to_datetime(db_sig["date"])
        src_sig = bundle.signals[sig_cols].reset_index(drop=True).copy()
        src_sig["date"] = pd.to_datetime(src_sig["date"])
        pd.testing.assert_frame_equal(db_sig, src_sig, check_exact=True, check_dtype=False)

    if bundle.influencer_sample is not None:
        n = conn.execute(select(func.count()).select_from(schema.influencer_sample)).scalar_one()
        assert n == len(bundle.influencer_sample), "influencer_sample row count mismatch"

    if bundle.city_economic is not None:
        n = conn.execute(select(func.count()).select_from(schema.city_economic_daily)).scalar_one()
        assert n == len(bundle.city_economic), "city_economic row count mismatch"


# ── Backup ──────────────────────────────────────────────────────────────────


def backup_sqlite(engine: Engine) -> Path | None:
    if not is_sqlite(engine) or not engine.url.database or engine.url.database == ":memory:":
        return None
    db_path = Path(engine.url.database)
    if not db_path.is_file() or db_path.stat().st_size == 0:
        return None
    backup_dir = settings.backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = backup_dir / f"optichain-{stamp}.sqlite3"
    raw = engine.raw_connection()
    try:
        dst = sqlite3.connect(target)
        try:
            raw.driver_connection.backup(dst)
        finally:
            dst.close()
    finally:
        raw.close()
    backups = sorted(backup_dir.glob("optichain-*.sqlite3"))
    for old in backups[: max(0, len(backups) - settings.db_backup_keep)]:
        old.unlink(missing_ok=True)
    logger.info("SQLite backup written: %s", target)
    return target


# ── Orchestration ───────────────────────────────────────────────────────────


def _merge_skus(conn: Connection, rows: list[dict[str, Any]]) -> None:
    for row in rows:
        updated = conn.execute(
            schema.skus.update()
            .where(schema.skus.c.sku_id == row["sku_id"])
            .values(
                brand_id=row["brand_id"],
                category=row["category"],
                brand_enc=row["brand_enc"],
                category_enc=row["category_enc"],
            )
        )
        if not updated.rowcount:
            conn.execute(schema.skus.insert().values(**row))


def _replace_keys(conn: Connection, table, rows: list[dict[str, Any]], keys: tuple[str, ...]) -> None:
    for row in rows:
        predicate = [table.c[key] == row[key] for key in keys]
        conn.execute(table.delete().where(*predicate))
    _insert_rows(conn, table, rows)


def _merge_incremental_rows(conn: Connection, rows: dict[str, list[dict[str, Any]]]) -> None:
    """Merge a monthly batch while retaining historical demand and signals."""
    _merge_skus(conn, rows["skus"])
    _replace_keys(conn, schema.demand_daily, rows["demand_daily"], ("sku_id", "date"))
    _replace_keys(conn, schema.signals, rows["signals"], ("sku_id", "date", "signal_type"))

    # Inventory and demo influencer data are snapshots without a date key.
    # A monthly batch must provide the complete current snapshot for these tables.
    if rows["inventory"]:
        conn.execute(schema.inventory.delete())
        _insert_rows(conn, schema.inventory, rows["inventory"])
    if rows["influencer_sample"]:
        conn.execute(schema.influencer_sample.delete())
        _insert_rows(conn, schema.influencer_sample, rows["influencer_sample"])
    if rows["documents"]:
        for row in rows["documents"]:
            conn.execute(schema.documents.delete().where(schema.documents.c.key == row["key"]))
        _insert_rows(conn, schema.documents, rows["documents"])
    if rows["city_economic_daily"]:
        conn.execute(schema.city_economic_daily.delete())
        _insert_rows(conn, schema.city_economic_daily, rows["city_economic_daily"])


def ingest(
    engine: Engine,
    trigger: str = "cli",
    backup: bool = True,
    mode: Literal["replace", "incremental"] = "replace",
) -> IngestReport:
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    run_migrations(engine)

    bundle = read_sources()
    warnings = validate(bundle)
    rows = build_rows(bundle)
    checksums = present_source_checksums()

    backup_path = backup_sqlite(engine) if backup and has_data(engine) else None

    if mode not in {"replace", "incremental"}:
        raise ValueError(f"unsupported ingest mode: {mode}")

    with engine.begin() as conn:
        if mode == "replace":
            for table in reversed(schema.DATA_TABLES):
                conn.execute(table.delete())
            conn.execute(schema.dataset_meta.delete())
            for table in schema.DATA_TABLES:
                batch = rows[table.name]
                _insert_rows(conn, table, batch)
            verify_loaded(conn, bundle)
        else:
            _merge_incremental_rows(conn, rows)

        run_id = conn.execute(
            schema.ingest_runs.insert().values(
                started_at=started_at,
                finished_at=datetime.now(timezone.utc).isoformat(),
                trigger=trigger,
                notes="; ".join(warnings),
            )
        ).inserted_primary_key[0]

        raw_demand = bundle.demand[["sku_id", "date", "brand_id", "category", "units_sold"]].copy()
        raw_demand["date"] = pd.to_datetime(raw_demand["date"]).dt.date
        raw_rows = _records(raw_demand)
        for row in raw_rows:
            row["ingest_run_id"] = run_id
        _insert_rows(conn, schema.raw_demand_daily, raw_rows)

        datasets = {
            bundle.demand_dataset: len(rows["demand_daily"]),
            "inventory": len(rows["inventory"]),
            "signals": len(rows["signals"]),
            "influencer_sample": len(rows["influencer_sample"]),
            "influencer_metrics": len(rows["documents"]),
            "city_economic": len(rows["city_economic_daily"]),
        }
        for name, count in datasets.items():
            if name not in checksums:
                continue
            values = {
                "dataset": name,
                "source_path": str(bundle.paths[name]),
                "source_sha256": checksums[name],
                "row_count": count,
                "ingest_run_id": run_id,
            }
            if mode == "incremental":
                conn.execute(schema.dataset_meta.delete().where(schema.dataset_meta.c.dataset == name))
            conn.execute(schema.dataset_meta.insert().values(**values))
            conn.execute(schema.dataset_loads.insert().values(**values))

    report = IngestReport(
        run_id=int(run_id),
        trigger=trigger,
        row_counts={name: len(batch) for name, batch in rows.items()},
        duration_s=round(time.perf_counter() - started, 3),
        backup_path=str(backup_path) if backup_path else None,
        warnings=warnings,
    )
    logger.info(
        "Ingest run %d (%s) committed in %.2fs: %s",
        report.run_id,
        trigger,
        report.duration_s,
        report.row_counts,
    )
    return report


def loaded_checksums(engine: Engine) -> dict[str, str]:
    with engine.connect() as conn:
        rows = conn.execute(select(schema.dataset_meta.c.dataset, schema.dataset_meta.c.source_sha256))
        return {name: sha for name, sha in rows}


def has_data(engine: Engine) -> bool:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(schema.ingest_runs)).scalar_one() > 0


def _insert_rows(conn: Connection, table, rows: list[dict[str, Any]]) -> None:
    """Insert rows in multi-value batches for remote PostgreSQL connections.

    pg8000 implements ``executemany`` as one network round trip per row.
    Compiling bounded multi-row INSERT statements keeps memory use predictable
    while reducing Supabase ingestion from tens of thousands of round trips to
    a few dozen.
    """
    if not rows:
        return
    if conn.dialect.name == "postgresql":
        columns = list(rows[0])
        quote = conn.dialect.identifier_preparer.quote
        payload = io.StringIO()
        writer = csv.writer(payload, lineterminator="\n")
        for row in rows:
            writer.writerow(
                [
                    "\\N" if row[column] is None else row[column]
                    for column in columns
                ]
            )
        payload.seek(0)
        raw = conn.connection.driver_connection
        raw.cursor().execute(
            f"COPY {quote(table.name)} ({', '.join(quote(c) for c in columns)}) "
            "FROM STDIN WITH (FORMAT CSV, NULL '\\N')",
            stream=payload,
        )
        logger.info("Inserted %s: %d/%d rows via COPY", table.name, len(rows), len(rows))
        return

    batch_size = len(rows)
    total = len(rows)
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        conn.execute(table.insert(), batch)
        logger.info("Inserted %s: %d/%d rows", table.name, min(start + batch_size, total), total)


def ingest_reason(engine: Engine) -> str | None:
    """Why the database needs (re)loading, or None when it is current."""
    if not has_data(engine):
        return "database is empty"
    if settings.db_auto_refresh:
        current = present_source_checksums()
        loaded = loaded_checksums(engine)
        if current != loaded:
            changed = sorted(k for k in set(current) | set(loaded) if current.get(k) != loaded.get(k))
            return f"source files changed: {changed}"
    return None


def ensure_database(engine: Engine) -> str:
    """Migrate, then load or refresh data when needed. Returns a status line."""
    run_migrations(engine)
    if not settings.db_auto_init:
        return "auto-init disabled"
    reason = ingest_reason(engine)
    if reason is None:
        return "database current"
    logger.info("Loading database: %s", reason)
    report = ingest(engine, trigger="startup")
    return f"loaded ({reason}) in {report.duration_s}s"


def main(argv: list[str] | None = None) -> int:
    from app.core.logging import configure_logging
    from app.db.engine import get_engine

    ap = argparse.ArgumentParser(description="Load the CSV sources into the serving database.")
    ap.add_argument("--no-backup", action="store_true", help="skip the SQLite backup step")
    ap.add_argument("--force", action="store_true", help="reload even if sources are unchanged")
    ap.add_argument(
        "--incremental",
        action="store_true",
        help="merge demand and signal rows while refreshing snapshot datasets",
    )
    args = ap.parse_args(argv)

    configure_logging(settings.log_level)
    engine = get_engine()
    run_migrations(engine)
    reason = ingest_reason(engine)
    if reason is None and not args.force:
        print("Database already current; use --force to reload.")
        return 0
    try:
        report = ingest(
            engine,
            trigger="cli",
            backup=not args.no_backup,
            mode="incremental" if args.incremental else "replace",
        )
    except IngestValidationError as e:
        print(f"Validation failed, database untouched: {e}", file=sys.stderr)
        return 2
    print(json.dumps(report.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
