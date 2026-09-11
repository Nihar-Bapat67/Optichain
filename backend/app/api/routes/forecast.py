"""Three-model demand forecasting agent and influencer model metrics."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.logging import get_logger
from app.core.state import registry
from app.schemas import ForecastRequest, ForecastResponse
from app.services import tables
from app.services.demand_agent import run_forecast_agent

logger = get_logger(__name__)
router = APIRouter(tags=["forecast"])


@router.get("/api/influencer/summary", summary="MODEL2 metrics and sample distribution")
def influencer_summary() -> dict[str, Any]:
    metrics = tables.load_influencer_metrics()
    sample = tables.load_influencer_sample()

    out: dict[str, Any] = {
        "metrics": metrics,
        "models_loaded": list(registry.model2.keys()),
        "sample_rows": 0,
        "distribution": None,
    }

    if sample is not None and not sample.empty and "peak_lift_pct" in sample.columns:
        out["sample_rows"] = len(sample)
        pred_col = "peak_lift_pct_pred" if "peak_lift_pct_pred" in sample.columns else None
        if pred_col:
            out["distribution"] = {
                "peak_lift_pct_actual_mean": float(sample["peak_lift_pct"].mean()),
                "peak_lift_pct_pred_mean": float(sample[pred_col].mean()),
            }

    return out


@router.post(
    "/api/demand/forecast",
    response_model=ForecastResponse,
    summary="Run the baseline × influencer uplift × city growth pipeline",
)
def demand_forecast(body: ForecastRequest) -> ForecastResponse:
    """Three-model demand forecasting agent endpoint."""
    result = run_forecast_agent(
        product_id=body.product_id,
        city=body.city,
        date=body.date,
        influencer=body.influencer.model_dump() if body.influencer else None,
        campaign_active=body.campaign_active,
        models=registry.as_agent_payload(),
    )
    return ForecastResponse(**result)
