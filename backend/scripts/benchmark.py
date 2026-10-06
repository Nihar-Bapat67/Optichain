"""In-process latency benchmark and response snapshotter for the API.

Usage (from backend/):
    python scripts/benchmark.py --out results.json [--snapshots DIR] [--iterations 20]

Runs every endpoint through FastAPI's TestClient (lifespan included), so the
numbers measure server-side handler time without network noise. With
--snapshots, each endpoint's response body is also written to DIR so two runs
can be diffed to prove responses are unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

FORECAST_CAMPAIGN = {
    "product_id": "WS-CU-002",
    "city": "Mumbai",
    "date": "2024-11-29",
    "influencer": {"id": "inf-1", "followers": 250000, "engagement_rate": 0.045, "platform": "instagram"},
    "campaign_active": True,
}
FORECAST_PLAIN = {"product_id": "PB-BD-001", "city": "London", "date": "2024-06-15", "campaign_active": False}

# (name, method, path, json body)
CASES: list[tuple[str, str, str, dict | None]] = [
    ("health", "GET", "/api/health", None),
    ("meta_skus", "GET", "/api/meta/skus", None),
    ("inventory_summary", "GET", "/api/inventory/summary", None),
    ("demand_ts", "GET", "/api/demand/timeseries?sku_id=PB-BD-001", None),
    ("demand_ts_range", "GET", "/api/demand/timeseries?sku_id=PB-BD-001&from=2024-10-01&to=2024-12-31", None),
    ("demand_ts_404", "GET", "/api/demand/timeseries?sku_id=NOPE", None),
    ("signals_ts_sku", "GET", "/api/signals/timeseries?sku_id=PB-BD-001", None),
    ("signals_ts_all", "GET", "/api/signals/timeseries", None),
    ("kpis", "GET", "/api/kpis/dashboard", None),
    ("risk_skus", "GET", "/api/risk/skus", None),
    ("brief_weekly", "GET", "/api/brief/weekly", None),
    ("influencer_summary", "GET", "/api/influencer/summary", None),
    ("simulate", "POST", "/api/simulate", {"sku_id": "PB-BD-001", "warehouse_id": "W1"}),
    (
        "simulate_adjusted",
        "POST",
        "/api/simulate",
        {"sku_id": "WS-CU-002", "warehouse_id": "W2", "extra_on_order": 500, "lead_time_delta_days": 5},
    ),
    ("simulate_404", "POST", "/api/simulate", {"sku_id": "NOPE", "warehouse_id": "W1"}),
    ("forecast_campaign", "POST", "/api/demand/forecast", FORECAST_CAMPAIGN),
    ("forecast_plain", "POST", "/api/demand/forecast", FORECAST_PLAIN),
]

VOLATILE_KEYS = {"generated_at"}


def _strip_volatile(obj):
    if isinstance(obj, dict):
        return {k: _strip_volatile(v) for k, v in obj.items() if k not in VOLATILE_KEYS}
    if isinstance(obj, list):
        return [_strip_volatile(v) for v in obj]
    return obj


def canonical(body) -> str:
    return json.dumps(_strip_volatile(body), sort_keys=True, separators=(",", ":"))


def digest(body) -> str:
    return hashlib.sha256(canonical(body).encode()).hexdigest()


def _call(client: TestClient, method: str, path: str, body: dict | None):
    return client.get(path) if method == "GET" else client.post(path, json=body)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--snapshots")
    ap.add_argument("--iterations", type=int, default=20)
    args = ap.parse_args()

    t0 = time.perf_counter()
    from app.main import app

    results: dict = {"iterations": args.iterations, "endpoints": {}}
    with TestClient(app) as client:
        results["startup_s"] = round(time.perf_counter() - t0, 3)
        snap_dir = Path(args.snapshots) if args.snapshots else None
        if snap_dir:
            snap_dir.mkdir(parents=True, exist_ok=True)

        for name, method, path, body in CASES:
            s = time.perf_counter()
            first = _call(client, method, path, body)
            first_ms = (time.perf_counter() - s) * 1000
            payload = first.json()
            if snap_dir:
                (snap_dir / f"{name}.json").write_text(canonical(payload), encoding="utf-8")

            timings = []
            for _ in range(args.iterations):
                s = time.perf_counter()
                _call(client, method, path, body)
                timings.append((time.perf_counter() - s) * 1000)
            timings.sort()
            results["endpoints"][name] = {
                "status": first.status_code,
                "sha256": digest(payload),
                "bytes": len(first.content),
                "first_ms": round(first_ms, 2),
                "mean_ms": round(statistics.mean(timings), 2),
                "p50_ms": round(statistics.median(timings), 2),
                "p95_ms": round(timings[max(0, int(len(timings) * 0.95) - 1)], 2),
            }
            r = results["endpoints"][name]
            print(
                f"{name:20s} {r['status']}  first {r['first_ms']:9.2f} ms  "
                f"p50 {r['p50_ms']:9.2f} ms  p95 {r['p95_ms']:9.2f} ms  {r['bytes']:>9} B"
            )

    Path(args.out).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"startup {results['startup_s']} s -> {args.out}")


if __name__ == "__main__":
    main()
