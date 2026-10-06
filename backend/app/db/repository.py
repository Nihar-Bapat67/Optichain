"""Read side of the serving database, with a data-version-aware cache.

Source data only changes when an ingest commits a new run, so derived results
(risk register, signal spikes, per-SKU frames) are memoised and invalidated
when `ingest_runs` advances. The version itself is re-checked at most every
`cache_version_ttl_s` seconds.

Row ordering matters for byte-identical responses: frames that previously came
straight from a CSV are returned in source order (`seq`), so any downstream
pandas operation sees exactly the input it used to.
"""

from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import date
from typing import Any, TypeVar

import pandas as pd
from sqlalchemy import Engine, func, select

from app.config import settings
from app.core.logging import get_logger
from app.db import schema
from app.db.engine import get_engine
from app.services.risk_engine import compute_risks, count_signal_spikes

logger = get_logger(__name__)

T = TypeVar("T")


class DataUnavailable(RuntimeError):
    """The database could not be initialised or holds no data."""


def _frame(engine: Engine, stmt) -> pd.DataFrame:
    with engine.connect() as conn:
        result = conn.execute(stmt)
        return pd.DataFrame(result.all(), columns=list(result.keys()))


class DataStore:
    def __init__(self, engine_provider: Callable[[], Engine] = get_engine) -> None:
        self._engine_provider = engine_provider
        self._lock = threading.RLock()
        self._memo: dict[Any, Any] = {}
        self._version: int | None = None
        self._checked_at = 0.0
        self.init_error: str | None = None
        self.init_status: str = "not initialised"

    @property
    def engine(self) -> Engine:
        return self._engine_provider()

    # ── Versioning / cache ──────────────────────────────────────────────────

    def _read_version(self) -> int | None:
        with self.engine.connect() as conn:
            return conn.execute(select(func.max(schema.ingest_runs.c.id))).scalar_one()

    def version(self) -> int | None:
        now = time.monotonic()
        if now - self._checked_at >= settings.cache_version_ttl_s:
            with self._lock:
                if now - self._checked_at >= settings.cache_version_ttl_s:
                    latest = self._read_version()
                    if latest != self._version:
                        if self._version is not None:
                            logger.info("Data version %s -> %s; cache cleared", self._version, latest)
                        self._memo.clear()
                        self._version = latest
                    self._checked_at = time.monotonic()
        return self._version

    def invalidate(self) -> None:
        with self._lock:
            self._memo.clear()
            self._checked_at = 0.0

    _RESPONSE_CACHE_SIZE = 512

    def response_bytes(self, key: str, render: Callable[[], bytes]) -> bytes:
        """Rendered JSON for a data-only GET, cached until the data version changes."""
        cache: OrderedDict[str, bytes] = self._cached("responses", OrderedDict)
        with self._lock:
            body = cache.get(key)
            if body is not None:
                cache.move_to_end(key)
                return body
        body = render()
        with self._lock:
            cache[key] = body
            while len(cache) > self._RESPONSE_CACHE_SIZE:
                cache.popitem(last=False)
        return body

    def _cached(self, key: Any, compute: Callable[[], T]) -> T:
        if self.init_error:
            raise DataUnavailable(self.init_error)
        self.version()
        try:
            return self._memo[key]
        except KeyError:
            pass
        with self._lock:
            if key not in self._memo:
                started = time.perf_counter()
                self._memo[key] = compute()
                logger.debug("cache fill %s in %.1fms", key, (time.perf_counter() - started) * 1000)
            return self._memo[key]

    # ── Dataset presence ────────────────────────────────────────────────────

    def datasets(self) -> dict[str, dict[str, Any]]:
        def load() -> dict[str, dict[str, Any]]:
            df = _frame(self.engine, select(schema.dataset_meta))
            return {r["dataset"]: r for r in df.to_dict("records")}

        return self._cached("datasets", load)

    def has_dataset(self, name: str) -> bool:
        try:
            return name in self.datasets()
        except DataUnavailable:
            return False

    def has_demand(self) -> bool:
        return self.has_dataset("demand_predictions") or self.has_dataset("ml_ready")

    # ── Catalogue ───────────────────────────────────────────────────────────

    def sku_table(self) -> pd.DataFrame:
        return self._cached(
            "skus", lambda: _frame(self.engine, select(schema.skus).order_by(schema.skus.c.sku_id))
        )

    def sku_list(self) -> list[dict[str, Any]]:
        return self._cached(
            "sku_list", lambda: self.sku_table()[["sku_id", "category"]].to_dict(orient="records")
        )

    def sku_profile(self, sku_id: str) -> dict[str, Any] | None:
        profiles = self._cached(
            "sku_profiles", lambda: {r["sku_id"]: r for r in self.sku_table().to_dict("records")}
        )
        return profiles.get(sku_id)

    def sku_exists(self, sku_id: str) -> bool:
        return self.sku_profile(sku_id) is not None

    # ── Demand ──────────────────────────────────────────────────────────────

    def demand_core(self) -> pd.DataFrame:
        """sku_id, date, units_sold, predicted_units for every SKU-day."""

        def load() -> pd.DataFrame:
            t = schema.demand_daily
            df = _frame(
                self.engine,
                select(t.c.sku_id, t.c.date, t.c.units_sold, t.c.predicted_units).order_by(t.c.sku_id, t.c.date),
            )
            df["date"] = pd.to_datetime(df["date"])
            df["predicted_units"] = df["predicted_units"].astype(float)
            return df

        return self._cached("demand_core", load)

    def demand_for_sku(self, sku_id: str) -> pd.DataFrame:
        """date-ascending rows for one SKU (empty frame for unknown SKUs)."""

        def load() -> pd.DataFrame:
            t = schema.demand_daily
            df = _frame(
                self.engine,
                select(t.c.date, t.c.units_sold, t.c.predicted_units)
                .where(t.c.sku_id == sku_id)
                .order_by(t.c.date),
            )
            df["date"] = pd.to_datetime(df["date"])
            df["predicted_units"] = df["predicted_units"].astype(float)
            return df

        return self._cached(("demand_sku", sku_id), load)

    def demand_date_range(self) -> tuple[date | None, date | None]:
        def load() -> tuple[date | None, date | None]:
            t = schema.demand_daily
            with self.engine.connect() as conn:
                lo, hi = conn.execute(select(func.min(t.c.date), func.max(t.c.date))).one()
            return lo, hi

        return self._cached("demand_range", load)

    def feature_row(self, sku_id: str, on: date) -> dict[str, Any] | None:
        """The stored MODEL1 feature vector for one SKU-day, if it exists."""
        t = schema.demand_daily
        cols = [t.c[c] for c in schema.DEMAND_FEATURE_COLUMNS]
        with self.engine.connect() as conn:
            row = conn.execute(
                select(*cols, t.c.predicted_units).where(t.c.sku_id == sku_id, t.c.date == on)
            ).mappings().first()
        return dict(row) if row else None

    # ── Inventory ───────────────────────────────────────────────────────────

    def inventory(self) -> pd.DataFrame:
        def load() -> pd.DataFrame:
            t = schema.inventory
            cols = [t.c.sku_id, t.c.warehouse_id, t.c.stock_on_hand, t.c.on_order, t.c.lead_time_days]
            return _frame(self.engine, select(*cols).order_by(t.c.seq))

        return self._cached("inventory", load)

    # ── Signals ─────────────────────────────────────────────────────────────

    _SIGNAL_COLS = ("date", "sku_id", "signal_type", "volume", "source")

    def _signals_query(self, sku_id: str | None) -> pd.DataFrame:
        t = schema.signals
        stmt = select(*[t.c[c] for c in self._SIGNAL_COLS]).order_by(t.c.seq)
        if sku_id is not None:
            stmt = stmt.where(t.c.sku_id == sku_id)
        df = _frame(self.engine, stmt)
        df["date"] = pd.to_datetime(df["date"])
        return df

    def signals_all(self) -> pd.DataFrame:
        return self._cached("signals_all", lambda: self._signals_query(None))

    def signals_for_sku(self, sku_id: str) -> pd.DataFrame:
        return self._cached(("signals_sku", sku_id), lambda: self._signals_query(sku_id))

    # ── Influencer ──────────────────────────────────────────────────────────

    def influencer_sample(self) -> pd.DataFrame | None:
        def load() -> pd.DataFrame | None:
            if not self.has_dataset("influencer_sample"):
                return None
            t = schema.influencer_sample
            df = _frame(self.engine, select(t.c.peak_lift_pct, t.c.peak_lift_pct_pred).order_by(t.c.seq))
            df["peak_lift_pct_pred"] = df["peak_lift_pct_pred"].astype(float)
            if df["peak_lift_pct_pred"].isna().all():
                df = df.drop(columns=["peak_lift_pct_pred"])
            return df

        return self._cached("influencer_sample", load)

    def influencer_metrics(self) -> dict | None:
        def load() -> dict | None:
            with self.engine.connect() as conn:
                body = conn.execute(
                    select(schema.documents.c.body).where(schema.documents.c.key == "influencer_metrics")
                ).scalar_one_or_none()
            return json.loads(body) if body is not None else None

        return self._cached("influencer_metrics", load)

    # ── Derived results ─────────────────────────────────────────────────────

    def risks(self) -> list[dict]:
        return self._cached("risks", lambda: compute_risks(self.demand_core(), self.inventory()))

    def signal_spikes(self) -> int:
        def load() -> int:
            if not self.has_dataset("signals"):
                return 0
            return count_signal_spikes(self.signals_all())

        return self._cached("signal_spikes", load)

    def summary(self) -> dict[str, Any]:
        def load() -> dict[str, Any]:
            lo, hi = self.demand_date_range()
            meta = self.datasets()
            with self.engine.connect() as conn:
                run = conn.execute(
                    select(schema.ingest_runs).order_by(schema.ingest_runs.c.id.desc()).limit(1)
                ).mappings().first()
            return {
                "data_version": self.version(),
                "loaded_at": run["finished_at"] if run else None,
                "backend": self.engine.dialect.name,
                "date_from": lo.isoformat() if lo else None,
                "date_to": hi.isoformat() if hi else None,
                "sku_count": len(self.sku_table()),
                "datasets": {
                    name: {"rows": m["row_count"], "sha256": m["source_sha256"][:12]} for name, m in meta.items()
                },
            }

        return self._cached("summary", load)

    def warm(self) -> None:
        """Populate the expensive cache entries before the first request."""
        started = time.perf_counter()
        self.sku_list()
        if self.has_dataset("inventory") and self.has_demand():
            self.risks()
        self.signal_spikes()
        self.influencer_sample()
        self.influencer_metrics()
        self.summary()
        logger.info("Cache warmed in %.2fs", time.perf_counter() - started)


store = DataStore()
