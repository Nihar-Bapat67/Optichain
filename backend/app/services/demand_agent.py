import hashlib
import math
import pandas as pd
import numpy as np
from typing import Any
from datetime import datetime

# ---------------------------------------------------------------------------
# City Profiles for Conti Model Synthesis
# ---------------------------------------------------------------------------
CITY_PROFILES = {
    "Mumbai": {"wealth": 1.2, "luxury_sensitivity": 1.4, "income": 55000, "house_price": 450000},
    "Delhi": {"wealth": 1.1, "luxury_sensitivity": 1.2, "income": 50000, "house_price": 380000},
    "Bangalore": {"wealth": 1.3, "luxury_sensitivity": 1.5, "income": 65000, "house_price": 420000},
    "Hyderabad": {"wealth": 1.15, "luxury_sensitivity": 1.1, "income": 48000, "house_price": 350000},
    "New York": {"wealth": 1.8, "luxury_sensitivity": 2.0, "income": 85000, "house_price": 850000},
    "London": {"wealth": 1.6, "luxury_sensitivity": 1.8, "income": 75000, "house_price": 750000},
    "Dubai": {"wealth": 2.0, "luxury_sensitivity": 2.2, "income": 95000, "house_price": 950000},
}
DEFAULT_PROFILE = {"wealth": 1.0, "luxury_sensitivity": 1.0, "income": 40000, "house_price": 300000}

LIFT_HOURS = [6, 12, 24, 48, 72, 96]

def _get_profile(city: str):
    return CITY_PROFILES.get(city, DEFAULT_PROFILE)


def _stable_hash(value: str) -> int:
    # Built-in hash() is salted per process (PYTHONHASHSEED), which made the same
    # request return different forecasts after every restart.
    return int(hashlib.md5(value.encode("utf-8")).hexdigest()[:8], 16)


def _synthesize_m1_features(
    product_id: str,
    city: str,
    date_str: str,
    feature_names: list[str],
    sku_profile: dict | None = None,
) -> pd.DataFrame:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    profile = _get_profile(city)

    if sku_profile is not None:
        # Catalogue SKU: use the encodings the model was trained with.
        brand_enc = int(sku_profile["brand_enc"])
        cat_enc = int(sku_profile["category_enc"])
    else:
        # Map brand/category based on SKU prefix for demo
        brand_enc = 0 if "WS" in product_id else 1 if "PB" in product_id else 2
        cat_enc = _stable_hash(product_id) % 10
    
    feats = {}
    for col in feature_names:
        if col == "month": feats[col] = dt.month
        elif col == "day_of_week": feats[col] = dt.weekday()
        elif col == "week_of_year": feats[col] = dt.isocalendar()[1]
        elif col == "quarter": feats[col] = (dt.month - 1) // 3 + 1
        elif col == "is_weekend": feats[col] = 1 if dt.weekday() >= 5 else 0
        elif col == "is_q4": feats[col] = 1 if dt.month >= 10 else 0
        elif col == "day_of_month": feats[col] = dt.day
        elif col == "brand_enc": feats[col] = brand_enc
        elif col == "category_enc": feats[col] = cat_enc
        elif "decay" in col or "overlap" in col or "pipeline" in col or "spring" in col:
            feats[col] = 0.0 # Default events to 0 for now
        elif "days_to" in col:
            feats[col] = 365 # Default to far away
        elif "lag" in col or "rolling" in col:
            feats[col] = 20.0 # Default baseline lag
        elif col == "trend_ratio_7_30":
            feats[col] = 1.0
        elif col == "ltv_tier_enc": feats[col] = 1
        elif col == "channel_enc": feats[col] = 2
        elif col == "is_gift_buyer": feats[col] = 0
        elif col == "is_registry_buyer": feats[col] = 0
        elif col == "conversion_rate": feats[col] = 0.85
        elif col == "active_registries": feats[col] = 0
        elif col == "items_fulfilled_this_month": feats[col] = 0
        else:
            feats[col] = 0.0
            
    return pd.DataFrame([feats])

def _synthesize_m2_features(influencer: dict, feature_names: list[str]) -> pd.DataFrame:
    # Influencer models in demo were trained on demo_feat_0..17
    # We map influencer stats to these floats
    n = len(feature_names)
    followers = float(influencer.get("followers") or 50000)
    eng_rate = float(influencer.get("engagement_rate") or 0.03)
    
    # Scale followers to a 0-1 range roughly
    reach = math.log10(max(followers, 1000)) / 7.0 # up to 10M
    
    data = {}
    for i, col in enumerate(feature_names):
        if i == 0: data[col] = reach
        elif i == 1: data[col] = eng_rate * 10
        elif i == 2: data[col] = 1.0 if influencer.get("platform") == "instagram" else 0.0
        elif col == "ws_flag": data[col] = 1
        else:
            # Deterministic noise for other demo feats
            data[col] = (_stable_hash(col) % 100) / 100.0
            
    return pd.DataFrame([data])

def _synthesize_conti_features(city: str, product_id: str, date_str: str, feature_names: list[str]) -> pd.DataFrame:
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    profile = _get_profile(city)
    
    # Conti features: day_of_year, month, median_income, median_home_price, 
    # affordability_ratio, income_velocity_30d, price_velocity_30d, rolling_units_30d, etc.
    
    base_feats = {
        "day_of_year": dt.timetuple().tm_yday,
        "month": dt.month,
        "median_income": profile["income"],
        "median_home_price": profile["house_price"],
        "affordability_ratio": profile["house_price"] / profile["income"],
        "income_velocity_30d": 0.02 * profile["wealth"], # Synthetic growth
        "price_velocity_30d": 0.01,
        "rolling_units_30d": 15.0,
    }
    
    # Handle dummy encoding if present in feature_names (e.g. city_City_B)
    data = {}
    for col in feature_names:
        if col in base_feats:
            data[col] = base_feats[col]
        elif col.startswith("city_"):
            target_city = col.split("_")[-1]
            data[col] = 1 if city == target_city else 0
        elif col == "category_Standard":
            data[col] = 0 # Assume Luxury by default
        else:
            data[col] = 0.0
            
    return pd.DataFrame([data])

def run_forecast_agent(
    product_id: str,
    city: str,
    date: str,
    influencer: dict | None,
    campaign_active: bool,
    models: dict[str, Any],
    sku_profile: dict | None = None,
    stored_features: dict | None = None,
) -> dict:
    """
    Execute the three-model pipeline using actual loaded ML artifacts.

    `stored_features` is the engineered feature row for this SKU-day from the
    training table; when given, MODEL1 sees exactly its training inputs.
    """
    insights: list[str] = []

    # 1. Baseline Model (XGBoost)
    m1 = models.get("model1")
    m1_feats = models.get("model1_feats")
    if m1 and m1_feats:
        if stored_features is not None and all(f in stored_features for f in m1_feats):
            X1 = pd.DataFrame([{f: stored_features[f] for f in m1_feats}])
            baseline = float(m1.predict(X1)[0])
            insights.append(
                f"Baseline from the stored engineered features for {product_id} on {date} "
                "(identical to the model's training inputs)."
            )
        else:
            X1 = _synthesize_m1_features(product_id, city, date, m1_feats, sku_profile)
            baseline = float(m1.predict(X1)[0])
            insights.append("Baseline demand synthesized from XGBoost signals.")
            if sku_profile is not None:
                insights.append(
                    "Date is outside the stored history, so lag and event features use defaults; "
                    "brand and category encodings come from the catalogue."
                )
    else:
        baseline = 150.0 # Fallback
        insights.append("⚠️ Baseline using fallback (Model 1 not loaded).")

    # 2. Influencer Model Bundle
    peak_lift_pct = 0.0
    lift_curve = [0.0] * len(LIFT_HOURS)
    decay_lambda = 0.0
    
    uplift_enabled = bool(campaign_active and influencer and influencer.get("id"))
    if uplift_enabled:
        bundle = models.get("model2_bundle", {})
        feat_map = models.get("model2_feats", {})
        
        if bundle and "peak_lift_pct" in bundle:
            # We assume all M2 models in the bundle share the same feature set structure
            first_target = list(feat_map.keys())[0] if feat_map else "peak_lift_pct"
            m2_feat_names = feat_map.get(first_target, [])
            X2 = _synthesize_m2_features(influencer, m2_feat_names)
            
            peak_lift_pct = float(bundle["peak_lift_pct"].predict(X2)[0])
            decay_lambda = float(bundle["decay_lambda"].predict(X2)[0])
            
            # Predict the curve
            curve_targets = ["lift_6h", "lift_24h", "lift_48h", "lift_72h", "lift_96h"]
            lift_curve = []
            for t in curve_targets:
                if t in bundle:
                    lift_curve.append(float(bundle[t].predict(X2)[0]))
                else:
                    lift_curve.append(0.0)
            
            plat = str(influencer.get("platform", "social")).capitalize()
            insights.append(f"{plat} campaign peak at {peak_lift_pct:.1f}% uplift (ML Pred).")
        else:
            insights.append("⚠️ Influencer models not loaded — using zero uplift.")
    else:
        insights.append("No active campaign — baseline demand applies.")

    # 3. City Growth Model (Conti / LGBM)
    mc = models.get("conti")
    mc_feats = models.get("conti_feats")
    if mc and mc_feats:
        Xc = _synthesize_conti_features(city, product_id, date, mc_feats)
        city_extra_units = float(mc.predict(Xc)[0])
        insights.append(f"City trend units optimized via Conti LGBM model.")
    else:
        city_extra_units = 5.0 # Fallback
        insights.append("⚠️ City growth using fallback (Conti model not loaded).")

    # Composite Calculations
    influencer_lift_units = round(baseline * (peak_lift_pct / 100.0), 2)
    final_demand = round(max(0.0, baseline + influencer_lift_units + city_extra_units), 2)

    return {
        "final_demand": final_demand,
        "breakdown": {
            "baseline": round(baseline, 2),
            "influencer_lift_units": influencer_lift_units,
            "city_growth_units": round(city_extra_units, 2),
        },
        "uplift": {
            "enabled": uplift_enabled,
            "peak_lift_pct": round(peak_lift_pct, 2),
            "lift_curve": [round(v, 3) for v in lift_curve],
            "decay_lambda": round(decay_lambda, 4),
        },
        "insights": insights,
    }
