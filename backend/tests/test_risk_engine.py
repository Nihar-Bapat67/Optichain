"""Risk engine business rules and the grouped-loop optimisation."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.config import settings
from app.services import risk_engine
from app.services.brief import build_weekly_brief
from app.services.risk_engine import compute_risks, count_signal_spikes


def _demand(sku: str, units: list[float], preds: list[float] | None = None) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=len(units), freq="D")
    return pd.DataFrame(
        {"date": dates, "sku_id": sku, "units_sold": units, "predicted_units": preds if preds else units}
    )


def _inv(rows: list[tuple]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["sku_id", "warehouse_id", "stock_on_hand", "on_order", "lead_time_days"])


def test_stockout_flagged_with_rising_trend():
    units = [10.0] * 21 + [20.0] * 7  # last-7 mean 20 vs prior-7 mean 10 → rising
    risks = compute_risks(_demand("A", units), _inv([("A", "W1", 100.0, 0.0, 30)]))
    assert len(risks) == 1
    r = risks[0]
    run_rate = np.mean(units[-28:])
    assert r["risk_type"] == "stockout"
    assert r["expected_demand_in_lead_time"] == round(run_rate * 30, 2)
    assert r["severity"] == round(min(1.0, run_rate * 30 / 100 - 1.0), 4)
    assert "Recent demand trend is rising." in r["reasons"]


def test_overstock_needs_high_cover_and_softening_trend():
    units = [10.0] * 21 + [5.0] * 7
    risks = compute_risks(_demand("B", units), _inv([("B", "W1", 5000.0, 0.0, 10)]))
    assert risks[0]["risk_type"] == "overstock"
    assert risks[0]["reasons"] == ["Weeks-of-cover is high while demand is softening."]

    flat = compute_risks(_demand("B", [10.0] * 28), _inv([("B", "W1", 5000.0, 0.0, 10)]))
    assert flat == []  # high cover but no softening → not flagged


def test_unknown_inventory_sku_is_skipped_and_order_is_by_severity():
    demand = pd.concat([_demand("A", [10.0] * 28), _demand("C", [50.0] * 28)])
    # A: 300 needed vs 200 → severity 0.5; C: 1500 vs 100 → capped at 1.0.
    inv = _inv([("A", "W1", 200.0, 0.0, 30), ("ZZ", "W1", 1.0, 0.0, 5), ("C", "W1", 100.0, 0.0, 30)])
    risks = compute_risks(demand, inv)
    assert [r["sku_id"] for r in risks] == ["C", "A"]
    assert risks[0]["severity"] >= risks[1]["severity"]


def _reference_compute_risks(demand, inventory, stockout_ratio_threshold=1.15,
                             overstock_weeks_threshold=10.0, trend_overstock_max=0.92):
    """The original per-row-mask implementation, kept verbatim as an oracle."""
    demand = demand.copy()
    demand["date"] = pd.to_datetime(demand["date"])
    results = []
    for _, row in inventory.copy().iterrows():
        sku, wh = str(row["sku_id"]), str(row["warehouse_id"])
        stock = float(row["stock_on_hand"]) + float(row["on_order"])
        lead = int(row["lead_time_days"])
        sku_d = demand[demand["sku_id"] == sku]
        if sku_d.empty:
            continue
        mean_act, mean_pred = risk_engine._mean_daily(sku_d)
        trend = risk_engine._trend_ratio(sku_d)
        run_rate = max(mean_act, mean_pred)
        expected = run_rate * lead
        woc = stock / max(run_rate * 7, 0.01)
        reasons, severity, rtype = [], 0.0, "ok"
        if expected > stock * stockout_ratio_threshold:
            rtype = "stockout"
            severity = min(1.0, expected / max(stock, 1) - 1.0)
            reasons.append("Projected demand during lead time exceeds available supply.")
            if trend > 1.05:
                reasons.append("Recent demand trend is rising.")
        elif woc > overstock_weeks_threshold and trend < trend_overstock_max:
            rtype = "overstock"
            severity = min(1.0, (woc - overstock_weeks_threshold) / overstock_weeks_threshold)
            reasons.append("Weeks-of-cover is high while demand is softening.")
        if rtype != "ok":
            results.append(risk_engine.RiskRow(sku, wh, rtype, severity, woc, expected, stock, lead, reasons))
    results.sort(key=lambda r: (-r.severity, r.risk_type))
    return [
        {
            "sku_id": r.sku_id, "warehouse_id": r.warehouse_id, "risk_type": r.risk_type,
            "severity": round(r.severity, 4), "weeks_of_cover": round(r.weeks_of_cover, 2),
            "expected_demand_in_lead_time": round(r.expected_demand_in_lead_time, 2),
            "available_units": round(r.available_units, 2), "lead_time_days": r.lead_time_days,
            "reasons": r.reasons,
        }
        for r in results
    ]


def test_optimised_engine_matches_original_on_real_data():
    demand = pd.read_csv(settings.demand_predictions_path(), parse_dates=["date"])
    inv = pd.read_csv(settings.inventory_path())
    assert compute_risks(demand, inv) == _reference_compute_risks(demand, inv)


def test_signal_spike_rule():
    dates = pd.date_range("2024-01-01", periods=14, freq="D")
    quiet = [100.0] * 7
    sig = pd.DataFrame(
        {
            "date": list(dates) * 2,
            "sku_id": ["S1"] * 14 + ["S2"] * 14,
            "volume": quiet + [200.0] * 7 + quiet + [120.0] * 7,
        }
    )
    assert count_signal_spikes(sig) == 1  # S1 doubled; S2 rose only 20 %
    assert count_signal_spikes(pd.DataFrame(columns=["date", "sku_id", "volume"])) == 0


def test_brief_counts_and_fallback_bullet():
    empty = build_weekly_brief([], 0)
    assert empty.bullets == ["No critical inventory exceptions detected in the current snapshot."]
    risks = [{"sku_id": "A", "warehouse_id": "W1", "risk_type": "stockout", "expected_demand_in_lead_time": 300.0,
              "lead_time_days": 30, "available_units": 100.0, "weeks_of_cover": 2.3}]
    brief = build_weekly_brief(risks, 4)
    assert (brief.stockout_count, brief.overstock_count, brief.signal_spikes) == (1, 0, 4)
    assert brief.bullets[0].startswith("Stockout risk: A @ W1")
