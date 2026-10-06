"""API contract tests.

Golden digests were recorded from the original CSV-backed implementation
(commit 99a382e). Every data endpoint must still return byte-identical bodies.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark import CASES, digest

GOLDEN = json.loads((Path(__file__).parent / "golden" / "contract_digests.json").read_text())


@pytest.mark.parametrize("name,method,path,body", [c for c in CASES if c[0] in GOLDEN], ids=lambda v: v if isinstance(v, str) else "")
def test_response_matches_original_implementation(client, name, method, path, body):
    resp = client.get(path) if method == "GET" else client.post(path, json=body)
    assert resp.status_code == GOLDEN[name]["status"]
    assert digest(resp.json()) == GOLDEN[name]["sha256"], f"{name} response changed"


def test_cached_response_is_stable(client):
    first = client.get("/api/risk/skus").content
    assert client.get("/api/risk/skus").content == first


def test_health_reports_database_backed_data(client):
    h = client.get("/api/health").json()
    assert h["ok"] is True
    assert h["demand_predictions_present"] and h["inventory_present"] and h["signals_present"]
    assert h["model1_loaded"] is True
    assert h["model2_targets_loaded"] == 7


def test_dataset_summary(client):
    d = client.get("/api/meta/dataset").json()
    assert d["backend"] == "sqlite"
    assert (d["date_from"], d["date_to"]) == ("2023-01-01", "2024-12-31")
    assert d["sku_count"] == 30
    assert d["datasets"]["demand_predictions"]["rows"] == 21930
    assert d["data_version"] >= 1


def test_signal_filters_match_client_side_filtering(client):
    full = client.get("/api/signals/timeseries?sku_id=PB-BD-001").json()["points"]
    expected = [p for p in full if p["signal_type"] == "social"][-90:]
    got = client.get("/api/signals/timeseries?sku_id=PB-BD-001&signal_type=social&limit=90").json()["points"]
    assert got == expected


@pytest.mark.parametrize(
    "path",
    [
        "/api/demand/timeseries?sku_id=PB-BD-001&from=not-a-date",
        "/api/signals/timeseries?to=2024-99-99",
        "/api/signals/timeseries?limit=0",
    ],
)
def test_bad_query_params_are_422(client, path):
    assert client.get(path).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"product_id": "PB-BD-001", "city": "Mumbai", "date": "2024-13-01"},
        {"product_id": "PB-BD-001", "city": "Mumbai", "date": "yesterday"},
        {"product_id": "", "city": "Mumbai", "date": "2024-01-01"},
        {
            "product_id": "PB-BD-001", "city": "Mumbai", "date": "2024-01-01", "campaign_active": True,
            "influencer": {"id": "x", "followers": -5},
        },
    ],
)
def test_bad_forecast_input_is_422(client, body):
    assert client.post("/api/demand/forecast", json=body).status_code == 422


def test_bad_simulation_input_is_422(client):
    body = {"sku_id": "PB-BD-001", "warehouse_id": "W1", "lead_time_delta_days": 99999}
    assert client.post("/api/simulate", json=body).status_code == 422


def test_simulation_arithmetic(client):
    inv = client.get("/api/inventory/summary").json()["rows"]
    row = next(r for r in inv if r["sku_id"] == "PB-BD-001" and r["warehouse_id"] == "W1")
    series = client.get("/api/demand/timeseries?sku_id=PB-BD-001").json()["points"]
    preds = [p["predicted_units"] for p in series][-14:]

    sim = client.post("/api/simulate", json={"sku_id": "PB-BD-001", "warehouse_id": "W1", "extra_on_order": 100}).json()
    remaining = row["stock_on_hand"] + row["on_order"] + 100
    for point, demand in zip(sim["points"], preds):
        remaining = max(0.0, remaining - demand)
        assert point["projected_stock"] == round(remaining, 2)


def test_data_unavailable_returns_503_and_health_degrades(client):
    from app.db.repository import store

    store.init_error = "simulated outage"
    try:
        assert client.get("/api/risk/skus").status_code == 503
        assert client.get("/api/kpis/dashboard").status_code == 503
        h = client.get("/api/health").json()
        assert h["ok"] is False
        assert "simulated outage" in h["messages"][0]
        assert client.get("/api/influencer/summary").status_code == 200
    finally:
        store.init_error = None
        store.invalidate()
    assert client.get("/api/kpis/dashboard").status_code == 200
