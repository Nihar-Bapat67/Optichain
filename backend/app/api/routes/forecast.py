"""Three-model demand forecasting agent and influencer model metrics."""

from __future__ import annotations

import json
import threading
from collections import OrderedDict
from datetime import date
from typing import Any

from fastapi import APIRouter

from app.core.logging import get_logger
from app.core.state import registry
from app.db.repository import DataUnavailable, store
from app.schemas import ForecastRequest, ForecastResponse
from app.services.demand_agent import run_forecast_agent
from app.services.quantile_forecast import predict_quantiles

logger = get_logger(__name__)
router = APIRouter(tags=["forecast"])

# Forecasts are deterministic given (request, data version), so identical
# requests are served from a small LRU instead of re-running seven models.
_FORECAST_CACHE_SIZE = 256
_forecast_cache: OrderedDict[str, dict] = OrderedDict()
_forecast_lock = threading.Lock()


@router.get("/api/influencer/summary", summary="MODEL2 metrics and sample distribution")
def influencer_summary() -> dict[str, Any]:
    try:
        metrics = store.influencer_metrics()
        sample = store.influencer_sample()
    except DataUnavailable:
        metrics, sample = None, None

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


def _history_for(product_id: str, on: str) -> tuple[dict | None, dict | None]:
    """Catalogue profile and stored feature row for a SKU-day, when available."""
    try:
        profile = store.sku_profile(product_id)
        if profile is None:
            return None, None
        return profile, store.feature_row(product_id, date.fromisoformat(on))
    except DataUnavailable:
        return None, None


@router.post(
    "/api/demand/forecast",
    response_model=ForecastResponse,
    response_model_exclude_none=True,
    summary="Run the baseline × influencer uplift × city growth pipeline",
)
def demand_forecast(body: ForecastRequest) -> ForecastResponse:
    """Three-model demand forecasting agent endpoint."""
    version = store.version() if not store.init_error else None
    key = json.dumps([version, body.model_dump()], sort_keys=True)
    with _forecast_lock:
        cached = _forecast_cache.get(key)
        if cached is not None:
            _forecast_cache.move_to_end(key)
            return ForecastResponse(**cached)

    profile, features = _history_for(body.product_id, body.date)
    result = run_forecast_agent(
        product_id=body.product_id,
        city=body.city,
        date=body.date,
        influencer=body.influencer.model_dump() if body.influencer else None,
        campaign_active=body.campaign_active,
        models=registry.as_agent_payload(),
        sku_profile=profile,
        stored_features=features,
    )
    if registry.quantiles_loaded:
        try:
            result.update(
                predict_quantiles(
                    models=registry.quantile_models,
                    feature_names=registry.quantile_features or [],
                    product_id=body.product_id,
                    city=body.city,
                    date=body.date,
                    sku_profile=profile,
                    stored_features=features,
                )
            )
            if registry.quantile_manifest:
                metadata = result["model_metadata"]
                metadata["training_cutoff"] = registry.quantile_manifest.get("training_cutoff")
                metadata["model_version"] = registry.quantile_manifest.get("model_version")
        except (ValueError, KeyError, TypeError, OSError) as exc:
            logger.exception("Quantile prediction unavailable for %s: %s", body.product_id, exc)

    with _forecast_lock:
        _forecast_cache[key] = result
        while len(_forecast_cache) > _FORECAST_CACHE_SIZE:
            _forecast_cache.popitem(last=False)
    return ForecastResponse(**result)
