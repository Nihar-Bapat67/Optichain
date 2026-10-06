"""SKU metadata and inventory positions."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response

from app.api.deps import cached_json
from app.core.logging import get_logger
from app.db.repository import store
from app.schemas import DatasetSummary

logger = get_logger(__name__)
router = APIRouter(tags=["catalog"])


@router.get("/api/meta/skus", summary="Distinct SKUs and their categories")
def meta_skus(request: Request) -> Response:
    def build() -> dict[str, Any]:
        if not store.has_demand():
            logger.warning("meta/skus requested but no demand data is available")
            raise HTTPException(503, "No demand data. Generate ws_demand_dataset and analytics first.")
        skus = store.sku_list()
        return {"skus": skus, "count": len(skus)}

    return cached_json(request, build)


@router.get(
    "/api/meta/dataset",
    response_model=DatasetSummary,
    summary="Loaded data version, history window and per-dataset row counts",
)
def meta_dataset() -> DatasetSummary:
    if not store.has_demand():
        raise HTTPException(503, "No demand data loaded.")
    return DatasetSummary(**store.summary())


@router.get("/api/inventory/summary", summary="Inventory rows and per-warehouse totals")
def inventory_summary(request: Request) -> Response:
    def build() -> dict[str, Any]:
        if not store.has_dataset("inventory"):
            logger.warning("inventory/summary requested but inventory data is missing")
            raise HTTPException(503, "No inventory.csv — run the ETL script.")

        inv = store.inventory().copy()
        inv["available"] = inv["stock_on_hand"] + inv["on_order"]
        by_wh = inv.groupby("warehouse_id").agg({"available": "sum", "sku_id": "nunique"}).reset_index()
        by_wh.columns = ["warehouse_id", "total_available_units", "sku_count"]
        return {
            "rows": inv.to_dict(orient="records"),
            "by_warehouse": by_wh.to_dict(orient="records"),
        }

    return cached_json(request, build)
