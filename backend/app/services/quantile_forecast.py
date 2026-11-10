from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from app.services.demand_agent import _synthesize_m1_features

QUANTILES = (0.1, 0.5, 0.9)


def _monotonic_values(raw: Mapping[float, float]) -> tuple[dict[str, float], bool]:
    values = np.array([float(raw[q]) for q in QUANTILES], dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("quantile model returned a non-finite prediction")
    values = np.maximum(values, 0.0)
    crossed = bool(np.any(np.diff(values) < 0))
    corrected = np.maximum.accumulate(values)
    return {
        "p10": float(corrected[0]),
        "p50": float(corrected[1]),
        "p90": float(corrected[2]),
    }, crossed


def predict_quantiles(
    models: Mapping[float, Any],
    feature_names: list[str],
    product_id: str,
    city: str,
    date: str,
    sku_profile: dict[str, Any] | None = None,
    stored_features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Predict daily conditional quantiles without changing the point forecast."""
    if set(models) != set(QUANTILES):
        raise ValueError("all P10/P50/P90 artifacts are required")
    if not feature_names:
        raise ValueError("quantile feature schema is empty")

    if stored_features is not None and all(name in stored_features for name in feature_names):
        frame = pd.DataFrame([{name: stored_features[name] for name in feature_names}])
    else:
        frame = _synthesize_m1_features(product_id, city, date, feature_names, sku_profile)

    frame = frame.replace([np.inf, -np.inf], np.nan).fillna(0)
    raw = {q: float(models[q].predict(frame)[0]) for q in QUANTILES}
    quantiles, crossed = _monotonic_values(raw)
    return {
        "quantiles": quantiles,
        "interval": {
            "nominal_coverage": 0.8,
            "lower": quantiles["p10"],
            "upper": quantiles["p90"],
        },
        "model_metadata": {
            "model_type": "lightgbm_quantile",
            "quantiles_available": True,
            "quantile_crossing_corrected": crossed,
        },
    }
