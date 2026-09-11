"""Time series and headline dashboard metrics."""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from app.api.deps import demand_frame
from app.core.logging import get_logger
from app.services import tables
from app.services.risk_engine import compute_risks, count_signal_spikes

logger = get_logger(__name__)
router = APIRouter(tags=["analytics"])


@router.get("/api/demand/timeseries", summary="Actual and predicted demand for one SKU")
def demand_timeseries(
    sku_id: str = Query(..., description="SKU identifier"),
    date_from: str | None = Query(None, alias="from", description="Inclusive ISO start date"),
    date_to: str | None = Query(None, alias="to", description="Inclusive ISO end date"),
) -> dict[str, Any]:
    df = demand_frame()
    if df is None:
        raise HTTPException(503, "No demand data available.")

    d = df[df["sku_id"] == sku_id].copy()
    if d.empty:
        raise HTTPException(404, f"Unknown sku_id: {sku_id}")

    d["date"] = pd.to_datetime(d["date"])
    if date_from:
        d = d[d["date"] >= pd.to_datetime(date_from)]
    if date_to:
        d = d[d["date"] <= pd.to_datetime(date_to)]
    d = d.sort_values("date")

    cols = ["date", "units_sold", "predicted_units"]
    use = [c for c in cols if c in d.columns]
    out = d[use].copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")

    return {"sku_id": sku_id, "points": out.to_dict(orient="records")}


@router.get("/api/signals/timeseries", summary="External social and search signal volume")
def signals_timeseries(
    sku_id: str | None = Query(None, description="Optional SKU filter"),
    date_from: str | None = Query(None, alias="from", description="Inclusive ISO start date"),
    date_to: str | None = Query(None, alias="to", description="Inclusive ISO end date"),
) -> dict[str, Any]:
    df = tables.load_signals()
    if df is None:
        raise HTTPException(503, "No signals.csv — run the ETL script.")

    s = df.copy()
    s["date"] = pd.to_datetime(s["date"])
    if sku_id:
        s = s[s["sku_id"] == sku_id]
    if date_from:
        s = s[s["date"] >= pd.to_datetime(date_from)]
    if date_to:
        s = s[s["date"] <= pd.to_datetime(date_to)]
    s = s.sort_values("date")
    s["date"] = s["date"].dt.strftime("%Y-%m-%d")

    return {"points": s.to_dict(orient="records")}


@router.get("/api/kpis/dashboard", summary="Headline counts for the dashboard KPI row")
def kpis_dashboard() -> dict[str, Any]:
    demand = demand_frame()
    inv = tables.load_inventory()
    sig = tables.load_signals()

    risks: list[dict] = []
    if demand is not None and inv is not None:
        risks = compute_risks(demand, inv)

    spikes = count_signal_spikes(sig) if sig is not None else 0

    return {
        "stockout_skus": len([r for r in risks if r["risk_type"] == "stockout"]),
        "overstock_skus": len([r for r in risks if r["risk_type"] == "overstock"]),
        "signal_spikes": spikes,
        "total_inventory_skus": len(inv) if inv is not None else 0,
    }
