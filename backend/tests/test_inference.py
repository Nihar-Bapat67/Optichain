"""ML inference: training/serving consistency and determinism."""

from __future__ import annotations

from datetime import date

import pytest

from app.core.state import registry
from app.db.repository import store
from app.services.demand_agent import (
    _stable_hash,
    _synthesize_m1_features,
    _synthesize_m2_features,
    run_forecast_agent,
)


@pytest.fixture(scope="module")
def models(client):
    assert registry.model1_loaded
    return registry.as_agent_payload()


@pytest.mark.parametrize(
    "sku,day",
    [("PB-BD-001", "2024-06-15"), ("WS-CU-002", "2024-11-29"), ("WE-RG-001", "2023-03-02"), ("WS-EL-002", "2024-12-31")],
)
def test_stored_features_reproduce_stored_prediction(models, sku, day):
    features = store.feature_row(sku, date.fromisoformat(day))
    assert features is not None
    out = run_forecast_agent(
        product_id=sku, city="Mumbai", date=day, influencer=None, campaign_active=False,
        models=models, sku_profile=store.sku_profile(sku), stored_features=features,
    )
    assert out["breakdown"]["baseline"] == pytest.approx(features["predicted_units"], abs=0.01)
    assert "stored engineered features" in out["insights"][0]


def test_known_sku_outside_history_uses_catalogue_encodings(models):
    profile = store.sku_profile("WS-SW-001")
    X = _synthesize_m1_features("WS-SW-001", "Mumbai", "2026-01-15", models["model1_feats"], profile)
    assert int(X["brand_enc"].iloc[0]) == profile["brand_enc"] == 0
    assert int(X["category_enc"].iloc[0]) == profile["category_enc"] == 10


def test_stable_hash_is_process_independent():
    # md5-derived, so the value cannot change between interpreter runs
    # (unlike built-in hash(), which is salted per process).
    import hashlib

    assert _stable_hash("SKU-WS-001") == int(hashlib.md5(b"SKU-WS-001").hexdigest()[:8], 16)


def test_m2_features_are_deterministic():
    names = [f"demo_feat_{i}" for i in range(18)] + ["ws_flag"]
    inf = {"followers": 250000, "engagement_rate": 0.045, "platform": "instagram"}
    a = _synthesize_m2_features(inf, names)
    b = _synthesize_m2_features(inf, names)
    assert a.equals(b)
    assert a["demo_feat_5"].iloc[0] == (_stable_hash("demo_feat_5") % 100) / 100.0


def test_forecast_composition(client):
    body = {
        "product_id": "WS-CU-002", "city": "London", "date": "2024-11-29", "campaign_active": True,
        "influencer": {"id": "i1", "followers": 500000, "engagement_rate": 0.05, "platform": "tiktok"},
    }
    r = client.post("/api/demand/forecast", json=body).json()
    b = r["breakdown"]
    # Components are rounded independently, so allow rounding slack.
    assert b["influencer_lift_units"] == pytest.approx(b["baseline"] * r["uplift"]["peak_lift_pct"] / 100.0, abs=0.05)
    assert r["final_demand"] == pytest.approx(b["baseline"] + b["influencer_lift_units"] + b["city_growth_units"], abs=0.02)
    assert len(r["uplift"]["lift_curve"]) == 5
    assert client.post("/api/demand/forecast", json=body).json() == r


def test_unknown_product_still_forecasts(client):
    r = client.post("/api/demand/forecast", json={"product_id": "SKU-NEW-999", "city": "Tokyo", "date": "2026-02-01"})
    assert r.status_code == 200
    assert r.json()["insights"][0] == "Baseline demand synthesized from XGBoost signals."
