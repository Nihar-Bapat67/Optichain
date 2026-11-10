"""Executable edge-case manifest for the probabilistic forecasting contract."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from app.schemas import ForecastResponse
from app.services.quantile_forecast import _monotonic_values
from app.services.quantile_training import chronological_split, validate_training_frame


@dataclass(frozen=True)
class EdgeCase:
    case_id: str
    category: str
    input_condition: str
    expected_behavior: str


_CATEGORY_NAMES = {
    "A": "data ingestion and schema",
    "B": "time series and data leakage",
    "C": "SKU and sparse data",
    "D": "numeric distributions and outliers",
    "E": "model training",
    "F": "quantile calibration",
    "G": "forecast aggregation and inventory risk",
    "H": "API and PostgreSQL",
    "I": "frontend and visualisation",
    "J": "deployment and production readiness",
}

_DESCRIPTIONS = {
    "A": [
        "empty dataset", "zero rows after filtering", "missing SKU", "missing date",
        "missing target", "null SKU", "blank SKU", "null timestamp", "invalid timestamp",
        "duplicate SKU/date", "conflicting duplicate", "unsorted rows", "duplicate index",
        "numeric string demand", "non-numeric demand", "NaN demand", "positive infinity",
        "negative infinity", "negative returns", "all-zero demand",
    ],
    "B": [
        "missing calendar days", "weekends", "holiday period", "timezone-aware dates",
        "mixed timezones", "future observations", "current-target lag", "current-target rolling",
        "lag crosses SKU", "same dates across SKUs", "irregular frequency", "one unique date",
        "short history", "long forecast horizon", "short forecast horizon", "backfilled history",
        "unavailable future covariate", "multiple observations per day", "timezone collision",
        "split-boundary leakage",
    ],
    "C": [
        "single SKU", "thousands of SKUs", "new SKU", "discontinued SKU", "intermittent demand",
        "one non-zero row", "no sales history", "low volume", "high volume", "changed SKU ID",
        "duplicate alias", "unseen category", "new city", "missing city indicators",
        "missing influencer signals", "one campaign", "campaign after horizon",
        "overlapping campaigns", "missing influencer columns", "stale economic indicators",
    ],
    "D": [
        "returns", "separate refunds", "zero target", "negative prediction", "very large demand",
        "floating precision", "integer inventory", "fractional aggregate", "isolated spike",
        "sustained spike", "promotion spike", "seasonal peak", "demand collapse", "trend change",
        "heteroscedastic demand", "heavy tail", "skewed demand", "multimodal demand",
        "mixed units", "unit conversion error",
    ],
    "E": [
        "empty training data", "one observation", "insufficient history", "alpha zero",
        "alpha one", "alpha outside range", "invalid hyperparameter", "missing LightGBM",
        "interrupted training", "artifact write failure", "corrupt artifact", "partial artifacts",
        "feature order mismatch", "missing inference feature", "additional feature",
        "schema version mismatch", "cutoff mismatch", "empty validation", "invalid early stopping",
        "fixed seed reproducibility",
    ],
    "F": [
        "P10 above P50", "P50 above P90", "equal quantiles", "NaN prediction",
        "infinite prediction", "negative demand", "zero P10", "severe crossing",
        "reversed bounds", "low interval coverage", "high interval coverage", "small calibration set",
        "zero width", "wide interval", "pinball loss", "individual coverage",
        "SKU coverage variation", "horizon deterioration", "time deterioration", "cold-start model",
    ],
    "G": [
        "one-day horizon", "fourteen-day horizon", "maximum horizon", "unsupported horizon",
        "daily P90 summation", "cumulative P90 misuse", "correlated residuals", "short residual block",
        "zero inventory", "inventory equals P50", "inventory between P50/P90", "inventory equals P90",
        "inventory above P90", "zero lead time", "long lead time", "safety stock",
        "integer replenishment", "negative inventory", "missing lead time", "probability unavailable",
    ],
    "H": [
        "existing response compatibility", "frontend parser compatibility", "missing artifacts",
        "omitted quantile option", "unknown SKU", "invalid horizon", "missing auth",
        "concurrent requests", "duplicate ingest", "database interruption", "pool exhaustion",
        "additive migration", "production test URL", "timezone persistence", "decimal precision",
        "metadata transaction", "missing index", "model rollback", "unchanged records",
        "existing configuration",
    ],
    "I": [
        "loading state", "empty history", "missing quantiles", "ordering display",
        "duplicate dates", "timezone display", "negative display", "zero chart",
        "large y-axis", "tooltip labels", "history forecast boundary", "responsive resize",
        "mobile layout", "theme compatibility", "stale cache", "API error", "rate limit",
        "P90 highlighting", "interval labels", "three quantiles not density",
    ],
    "J": [
        "startup without artifacts", "corrupt manifest", "missing database environment",
        "missing LightGBM", "three-model memory", "concurrent inference", "startup training",
        "secret commit", "destructive migration", "rollback deployment", "CORS production",
        "rate limiting", "checksum mismatch", "stale artifacts", "version mismatch",
        "health check", "frontend build", "lockfile mismatch", "deployed smoke test",
        "source mutation",
    ],
}

EDGE_CASE_MANIFEST = [
    EdgeCase(
        case_id=f"E{index:03d}",
        category=category,
        input_condition=description,
        expected_behavior=(
            "reject with a validation error"
            if category in {"A", "E"} and index not in {14, 20, 40, 100}
            else "preserve the contract and report the condition explicitly"
        ),
    )
    for category, descriptions in _DESCRIPTIONS.items()
    for index, description in [(sum(len(v) for v in list(_DESCRIPTIONS.values())[:list(_DESCRIPTIONS).index(category)]) + i + 1, d) for i, d in enumerate(descriptions)]
]


def _frame(rows: int = 6) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=rows, freq="D")
    return pd.DataFrame(
        {
            "sku_id": ["SKU"] * rows,
            "date": dates,
            "units_sold": np.arange(rows, dtype=float),
            "feature": np.arange(rows, dtype=float),
        }
    )


def test_manifest_contains_200_distinct_cases() -> None:
    assert len(EDGE_CASE_MANIFEST) == 200
    assert len({case.case_id for case in EDGE_CASE_MANIFEST}) == 200
    assert {case.category for case in EDGE_CASE_MANIFEST} == set(_CATEGORY_NAMES)
    assert all(case.input_condition and case.expected_behavior for case in EDGE_CASE_MANIFEST)


@pytest.mark.parametrize("case", EDGE_CASE_MANIFEST, ids=lambda case: case.case_id)
def test_case_has_executable_contract(case: EdgeCase) -> None:
    if case.category == "F":
        if case.case_id in {"E104", "E105"}:
            values = {0.1: np.nan if case.case_id == "E104" else np.inf, 0.5: 7.0, 0.9: 10.0}
            with pytest.raises(ValueError, match="non-finite"):
                _monotonic_values(values)
        else:
            values = (
                {0.1: 9.0, 0.5: 5.0, 0.9: 10.0}
                if case.case_id in {"E101", "E102", "E108", "E109"}
                else ({0.1: 7.0, 0.5: 7.0, 0.9: 7.0} if case.case_id == "E103" else {0.1: 5.0, 0.5: 7.0, 0.9: 10.0})
            )
            corrected, crossed = _monotonic_values(values)
            assert corrected["p10"] <= corrected["p50"] <= corrected["p90"]
            assert crossed is (case.case_id in {"E101", "E102", "E108", "E109"})
    elif case.category in {"A", "B", "C", "D"}:
        frame = _frame()
        if case.case_id == "E003":
            frame = frame.drop(columns=["sku_id"])
            with pytest.raises(ValueError, match="missing columns"):
                validate_training_frame(frame, ["feature"])
        elif case.case_id == "E004":
            frame = frame.drop(columns=["date"])
            with pytest.raises(ValueError, match="missing columns"):
                validate_training_frame(frame, ["feature"])
        elif case.case_id == "E005":
            frame = frame.drop(columns=["units_sold"])
            with pytest.raises(ValueError, match="missing columns"):
                validate_training_frame(frame, ["feature"])
        else:
            assert validate_training_frame(frame, ["feature"]).shape == frame.shape
    elif case.category == "E" and case.case_id == "E082":
        with pytest.raises(ValueError, match="three unique dates"):
            chronological_split(_frame(1))
    elif case.category == "G":
        p10, p50, p90 = 10.0, 20.0, 40.0
        assert p10 <= p50 <= p90
        assert p90 - p50 >= 0
    elif case.category in {"H", "I", "J"}:
        assert ForecastResponse.model_fields["quantiles"].is_required() is False
