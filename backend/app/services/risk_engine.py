from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class RiskRow:
    sku_id: str
    warehouse_id: str
    risk_type: str
    severity: float
    weeks_of_cover: float
    expected_demand_in_lead_time: float
    available_units: float
    lead_time_days: int
    reasons: list[str]


def _mean_daily(
    sku_df: pd.DataFrame,
    col_actual: str = "units_sold",
    col_pred: str = "predicted_units",
) -> tuple[float, float]:
    """Recent mean daily actual and predicted (last 28 rows if available)."""
    tail = sku_df.sort_values("date").tail(28)
    if tail.empty:
        return 0.01, 0.01
    ma = float(tail[col_actual].mean()) if col_actual in tail else 0.01
    mp = float(tail[col_pred].mean()) if col_pred in tail.columns else ma
    if np.isnan(mp):
        mp = ma
    return max(ma, 0.01), max(mp, 0.01)


def _trend_ratio(sku_df: pd.DataFrame) -> float:
    """>1 means demand up; <1 means down."""
    s = sku_df.sort_values("date")
    if len(s) < 15:
        return 1.0
    a = s["units_sold"].tail(7).mean()
    b = s["units_sold"].iloc[-14:-7].mean()
    if b <= 0:
        return 1.0
    return float(a / b)


def compute_risks(
    demand: pd.DataFrame,
    inventory: pd.DataFrame,
    stockout_ratio_threshold: float = 1.15,
    overstock_weeks_threshold: float = 10.0,
    trend_overstock_max: float = 0.92,
) -> list[dict]:
    demand = demand.copy()
    demand["date"] = pd.to_datetime(demand["date"])
    inv = inventory.copy()

    results: list[RiskRow] = []

    # One pass instead of a full-table mask per inventory row; groupby keeps each
    # SKU's rows in their original order, so the per-SKU frames are unchanged.
    by_sku = {str(sku): g for sku, g in demand.groupby("sku_id", sort=False)}

    for _, row in inv.iterrows():
        sku = str(row["sku_id"])
        wh = str(row["warehouse_id"])
        stock = float(row["stock_on_hand"]) + float(row["on_order"])
        lead = int(row["lead_time_days"])

        sku_d = by_sku.get(sku)
        if sku_d is None or sku_d.empty:
            continue

        mean_act, mean_pred = _mean_daily(sku_d)
        trend = _trend_ratio(sku_d)
        # Use max of actual and predicted run-rate for conservative stockout view
        run_rate = max(mean_act, mean_pred)
        expected = run_rate * lead
        woc = stock / max(run_rate * 7, 0.01)

        reasons: list[str] = []
        severity = 0.0
        rtype = "ok"

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
            results.append(
                RiskRow(
                    sku_id=sku,
                    warehouse_id=wh,
                    risk_type=rtype,
                    severity=severity,
                    weeks_of_cover=woc,
                    expected_demand_in_lead_time=expected,
                    available_units=stock,
                    lead_time_days=lead,
                    reasons=reasons,
                )
            )

    results.sort(key=lambda r: (-r.severity, r.risk_type))
    return [
        {
            "sku_id": r.sku_id,
            "warehouse_id": r.warehouse_id,
            "risk_type": r.risk_type,
            "severity": round(r.severity, 4),
            "weeks_of_cover": round(r.weeks_of_cover, 2),
            "expected_demand_in_lead_time": round(r.expected_demand_in_lead_time, 2),
            "available_units": round(r.available_units, 2),
            "lead_time_days": r.lead_time_days,
            "reasons": r.reasons,
        }
        for r in results
    ]


def count_signal_spikes(signals: pd.DataFrame, days: int = 7) -> int:
    if signals is None or signals.empty:
        return 0
    s = signals.copy()
    s["date"] = pd.to_datetime(s["date"])
    end = s["date"].max()
    if pd.isna(end):
        return 0
    recent = s[s["date"] > end - pd.Timedelta(days=days)]
    prior = s[(s["date"] <= end - pd.Timedelta(days=days)) & (s["date"] > end - pd.Timedelta(days=days * 2))]
    if recent.empty or prior.empty:
        return 0
    rmean = recent.groupby("sku_id")["volume"].mean()
    pmean = prior.groupby("sku_id")["volume"].mean()
    joined = rmean.to_frame("r").join(pmean.to_frame("p"), how="inner")
    if joined.empty:
        return 0
    spikes = (joined["r"] > joined["p"] * 1.5) & (joined["r"] > 100)
    return int(spikes.sum())
