"""Risk register, weekly brief and the what-if inventory simulation."""

from __future__ import annotations

from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException, Request, Response

from app.api.deps import cached_json
from app.core.logging import get_logger
from app.core.state import registry
from app.db.repository import store
from app.schemas import BriefResponse, SimulatePoint, SimulateRequest, SimulateResponse
from app.services.brief import build_weekly_brief
from app.services.quantile_forecast import predict_quantiles

logger = get_logger(__name__)
router = APIRouter(tags=["risk"])


def _add_quantile_context(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not registry.quantiles_loaded:
        return risks
    enriched: list[dict[str, Any]] = []
    for risk in risks:
        item = dict(risk)
        history = store.demand_for_sku(risk["sku_id"])
        if history.empty:
            enriched.append(item)
            continue
        last = history.sort_values("date").iloc[-1]
        profile = store.sku_profile(risk["sku_id"])
        try:
            forecast = predict_quantiles(
                models=registry.quantile_models,
                feature_names=registry.quantile_features or [],
                product_id=risk["sku_id"],
                city="",
                date=pd.Timestamp(last["date"]).strftime("%Y-%m-%d"),
                sku_profile=profile,
            )
        except (ValueError, KeyError, TypeError, OSError) as exc:
            logger.exception("Could not add quantile risk context for %s: %s", risk["sku_id"], exc)
            enriched.append(item)
            continue
        values = forecast["quantiles"]
        item.update(
            {
                "p10_demand": values["p10"],
                "p50_demand": values["p50"],
                "p90_demand": values["p90"],
                "safety_stock": max(0.0, values["p90"] - values["p50"]),
                "stockout_probability": None,
                "risk_basis": "daily quantile threshold; no cumulative scenario probability available",
            }
        )
        enriched.append(item)
    return enriched


def _require_demand_and_inventory(message: str) -> None:
    if not (store.has_demand() and store.has_dataset("inventory")):
        raise HTTPException(503, message)


@router.get("/api/risk/skus", summary="Stockout and overstock flags per SKU × warehouse")
def risk_skus(request: Request) -> Response:
    def build() -> dict[str, Any]:
        _require_demand_and_inventory("Need demand predictions and inventory.csv.")
        risks = _add_quantile_context(store.risks())
        return {"risks": risks, "count": len(risks)}

    return cached_json(request, build)


@router.get("/api/brief/weekly", response_model=BriefResponse, summary="Weekly buyer brief")
def brief_weekly() -> BriefResponse:
    _require_demand_and_inventory("Need demand and inventory for brief generation.")
    return build_weekly_brief(store.risks(), store.signal_spikes())


@router.post(
    "/api/simulate",
    response_model=SimulateResponse,
    summary="Project 14-day inventory drawdown under adjusted assumptions",
)
def simulate(body: SimulateRequest) -> SimulateResponse:
    _require_demand_and_inventory("Need demand and inventory.")
    inv = store.inventory()

    row = inv[(inv["sku_id"] == body.sku_id) & (inv["warehouse_id"] == body.warehouse_id)]
    if row.empty:
        raise HTTPException(404, "SKU / warehouse combination not found.")

    r = row.iloc[0]
    stock = float(r["stock_on_hand"]) + float(r["on_order"]) + float(body.extra_on_order)
    lead = max(1, int(r["lead_time_days"]) + int(body.lead_time_delta_days))

    sku_d = store.demand_for_sku(body.sku_id)
    if sku_d.empty:
        raise HTTPException(404, "No demand history for SKU.")

    # High-fidelity simulation: Use the actual predicted sequence for the next 14 days
    future = sku_d[sku_d["predicted_units"].notna()].tail(14)
    if not future.empty and len(future) >= 14:
        daily_demands = future["predicted_units"].tolist()
        source_note = "Using daily variable forecasts from XGBoost model."
    else:
        # Fallback to mean if future sequence is short/missing
        run = float(sku_d.tail(28)["predicted_units"].fillna(sku_d.tail(28)["units_sold"]).mean())
        if pd.isna(run) or run <= 0:
            run = 5.0
        daily_demands = [run] * 14
        source_note = f"Using mean run-rate of {run:.1f} units (baseline)."

    assumptions = [
        source_note,
        f"Lead time baseline {int(r['lead_time_days'])}d adjusted by "
        f"{body.lead_time_delta_days}d → using {lead}d horizon for burn.",
        "Simulation incorporates SKU-specific consumption patterns and scheduled on-orders.",
    ]

    points: list[SimulatePoint] = []
    remaining = stock
    for day, demand_amt in enumerate(daily_demands, 1):
        remaining = max(0.0, remaining - float(demand_amt))
        points.append(SimulatePoint(day=day, projected_stock=round(remaining, 2)))

    return SimulateResponse(
        sku_id=body.sku_id,
        warehouse_id=body.warehouse_id,
        assumptions=assumptions,
        points=points,
        final_projected_stock=points[-1].projected_stock,
    )
