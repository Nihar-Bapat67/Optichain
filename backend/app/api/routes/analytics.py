"""Time series and headline dashboard metrics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.api.deps import cached_json, parse_date_param
from app.core.logging import get_logger
from app.db.repository import store

logger = get_logger(__name__)
router = APIRouter(tags=["analytics"])


@router.get("/api/demand/timeseries", summary="Actual and predicted demand for one SKU")
def demand_timeseries(
    request: Request,
    sku_id: str = Query(..., max_length=64, description="SKU identifier"),
    date_from: str | None = Query(None, alias="from", description="Inclusive ISO start date"),
    date_to: str | None = Query(None, alias="to", description="Inclusive ISO end date"),
) -> Response:
    def build() -> dict:
        start = parse_date_param(date_from, "from")
        end = parse_date_param(date_to, "to")
        if not store.has_demand():
            raise HTTPException(503, "No demand data available.")
        if not store.sku_exists(sku_id):
            raise HTTPException(404, f"Unknown sku_id: {sku_id}")

        d = store.demand_for_sku(sku_id)
        if start is not None:
            d = d[d["date"] >= start]
        if end is not None:
            d = d[d["date"] <= end]

        out = d[["date", "units_sold", "predicted_units"]].copy()
        out["date"] = out["date"].dt.strftime("%Y-%m-%d")
        # NULL predictions (ml_ready-only data) serialise as null rather than NaN.
        out = out.astype(object).where(out.notna(), None)
        return {"sku_id": sku_id, "points": out.to_dict(orient="records")}

    return cached_json(request, build)


@router.get("/api/signals/timeseries", summary="External social and search signal volume")
def signals_timeseries(
    request: Request,
    sku_id: str | None = Query(None, max_length=64, description="Optional SKU filter"),
    date_from: str | None = Query(None, alias="from", description="Inclusive ISO start date"),
    date_to: str | None = Query(None, alias="to", description="Inclusive ISO end date"),
    signal_type: str | None = Query(None, max_length=32, description="Optional type filter, e.g. social"),
    limit: int | None = Query(None, ge=1, le=100_000, description="Keep only the most recent N points"),
) -> Response:
    def build() -> dict:
        start = parse_date_param(date_from, "from")
        end = parse_date_param(date_to, "to")
        if not store.has_dataset("signals"):
            raise HTTPException(503, "No signals.csv — run the ETL script.")

        s = (store.signals_for_sku(sku_id) if sku_id else store.signals_all()).copy()
        if start is not None:
            s = s[s["date"] >= start]
        if end is not None:
            s = s[s["date"] <= end]
        s = s.sort_values("date")
        if signal_type:
            s = s[s["signal_type"] == signal_type]
        if limit:
            s = s.tail(limit)
        s["date"] = s["date"].dt.strftime("%Y-%m-%d")
        return {"points": s.to_dict(orient="records")}

    return cached_json(request, build)


@router.get("/api/kpis/dashboard", summary="Headline counts for the dashboard KPI row")
def kpis_dashboard(request: Request) -> Response:
    def build() -> dict:
        has_inventory = store.has_dataset("inventory")
        risks = store.risks() if store.has_demand() and has_inventory else []
        return {
            "stockout_skus": sum(1 for r in risks if r["risk_type"] == "stockout"),
            "overstock_skus": sum(1 for r in risks if r["risk_type"] == "overstock"),
            "signal_spikes": store.signal_spikes(),
            "total_inventory_skus": len(store.inventory()) if has_inventory else 0,
        }

    return cached_json(request, build)
