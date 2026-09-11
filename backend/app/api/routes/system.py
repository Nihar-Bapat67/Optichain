"""Service health and artifact availability."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.core.state import registry
from app.schemas import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/api/health", response_model=HealthResponse, summary="Service and artifact health")
def health() -> HealthResponse:
    """Report which datasets and models the API was able to load.

    Used by the dashboard to decide between the setup screen and the live view.
    """
    msgs = list(registry.load_messages)

    predictions_present = settings.demand_predictions_path().is_file()
    inventory_present = settings.inventory_path().is_file()
    signals_present = settings.signals_path().is_file()
    influencer_present = settings.influencer_metrics_path().is_file()

    if not predictions_present:
        msgs.append(
            "Run scripts/build_case_study_tables.py to create "
            "analytics/demand_with_predictions.csv"
        )

    return HealthResponse(
        ok=predictions_present and inventory_present and signals_present,
        model1_loaded=registry.model1_loaded,
        model2_targets_loaded=registry.model2_targets_loaded,
        conti_model_loaded=registry.conti_loaded,
        demand_predictions_present=predictions_present,
        inventory_present=inventory_present,
        signals_present=signals_present,
        influencer_metrics_present=influencer_present,
        messages=msgs[:20],
    )
