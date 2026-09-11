"""SKU metadata and inventory positions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import demand_frame
from app.core.logging import get_logger
from app.services import tables

logger = get_logger(__name__)
router = APIRouter(tags=["catalog"])


@router.get("/api/meta/skus", summary="Distinct SKUs and their categories")
def meta_skus() -> dict[str, Any]:
    df = demand_frame()
    if df is None:
        logger.warning("meta/skus requested but no demand data is available")
        raise HTTPException(503, "No demand data. Generate ws_demand_dataset and analytics first.")

    sub = df[["sku_id", "category"]].drop_duplicates().sort_values("sku_id")
    return {"skus": sub.to_dict(orient="records"), "count": len(sub)}


@router.get("/api/inventory/summary", summary="Inventory rows and per-warehouse totals")
def inventory_summary() -> dict[str, Any]:
    df = tables.load_inventory()
    if df is None:
        logger.warning("inventory/summary requested but inventory.csv is missing")
        raise HTTPException(503, "No inventory.csv — run the ETL script.")

    inv = df.copy()
    inv["available"] = inv["stock_on_hand"] + inv["on_order"]
    by_wh = inv.groupby("warehouse_id").agg({"available": "sum", "sku_id": "nunique"}).reset_index()
    by_wh.columns = ["warehouse_id", "total_available_units", "sku_count"]

    return {
        "rows": inv.to_dict(orient="records"),
        "by_warehouse": by_wh.to_dict(orient="records"),
    }
