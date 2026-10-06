from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    ok: bool
    model1_loaded: bool
    model2_targets_loaded: int
    conti_model_loaded: bool
    demand_predictions_present: bool
    inventory_present: bool
    signals_present: bool
    influencer_metrics_present: bool
    messages: list[str] = Field(default_factory=list)


class SimulateRequest(BaseModel):
    sku_id: str = Field(min_length=1, max_length=64)
    warehouse_id: str = Field("W1", min_length=1, max_length=32)
    extra_on_order: float = Field(0.0, ge=-1e9, le=1e9, allow_inf_nan=False)
    lead_time_delta_days: int = Field(0, ge=-3650, le=3650)


class SimulatePoint(BaseModel):
    day: int
    projected_stock: float


class SimulateResponse(BaseModel):
    sku_id: str
    warehouse_id: str
    assumptions: list[str]
    points: list[SimulatePoint]
    final_projected_stock: float


class BriefResponse(BaseModel):
    title: str
    summary: str
    bullets: list[str]
    stockout_count: int
    overstock_count: int
    signal_spikes: int
    generated_at: str


# ── Demand Forecast Agent ──────────────────────────────────────────────────

class InfluencerInput(BaseModel):
    id: str | None = Field(None, max_length=128)
    followers: float | None = Field(None, ge=0, le=1e10, allow_inf_nan=False)
    engagement_rate: float | None = Field(None, ge=0, le=100, allow_inf_nan=False)
    platform: str | None = Field(None, max_length=32)


class ForecastRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)
    city: str = Field(min_length=1, max_length=64)
    date: str
    influencer: InfluencerInput | None = None
    campaign_active: bool = False

    @field_validator("date")
    @classmethod
    def _iso_date(cls, value: str) -> str:
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            raise ValueError("date must be a valid calendar date in YYYY-MM-DD format") from None
        return value


class ForecastBreakdown(BaseModel):
    baseline: float
    influencer_lift_units: float
    city_growth_units: float


class ForecastUplift(BaseModel):
    enabled: bool
    peak_lift_pct: float
    lift_curve: list[float]
    decay_lambda: float


class ForecastResponse(BaseModel):
    final_demand: float
    breakdown: ForecastBreakdown
    uplift: ForecastUplift
    insights: list[str]


class DatasetInfo(BaseModel):
    rows: int
    sha256: str


class DatasetSummary(BaseModel):
    data_version: int | None
    loaded_at: str | None
    backend: str
    date_from: str | None
    date_to: str | None
    sku_count: int
    datasets: dict[str, DatasetInfo]
