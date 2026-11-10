from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

QUANTILES = (0.1, 0.5, 0.9)


@dataclass(frozen=True)
class QuantileTrainingResult:
    manifest: dict[str, Any]
    metrics: dict[str, Any]


def validate_training_frame(frame: pd.DataFrame, feature_names: list[str], target: str = "units_sold") -> pd.DataFrame:
    required = {"sku_id", "date", target, *feature_names}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"training data is missing columns: {missing}")
    out = frame.copy()
    if not out.index.is_unique:
        raise ValueError("training data index must be unique")
    out["date"] = pd.to_datetime(out["date"], errors="raise")
    if out[["sku_id", "date"]].duplicated().any():
        raise ValueError("training data contains duplicate SKU/date rows")
    if not out.sort_values(["sku_id", "date"]).index.equals(out.index):
        raise ValueError("training data must be ordered by sku_id and date")
    if not np.isfinite(pd.to_numeric(out[target], errors="raise")).all():
        raise ValueError("training target contains NaN or infinity")
    return out


def chronological_split(frame: pd.DataFrame, validation_fraction: float = 0.15, test_fraction: float = 0.15) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if not 0 < validation_fraction < 1 or not 0 < test_fraction < 1 or validation_fraction + test_fraction >= 1:
        raise ValueError("validation and test fractions must leave a non-empty training split")
    dates = sorted(frame["date"].drop_duplicates())
    if len(dates) < 3:
        raise ValueError("at least three unique dates are required")
    train_end = max(1, int(len(dates) * (1 - validation_fraction - test_fraction)))
    validation_end = max(train_end + 1, int(len(dates) * (1 - test_fraction)))
    train_dates = set(dates[:train_end])
    validation_dates = set(dates[train_end:validation_end])
    test_dates = set(dates[validation_end:])
    if not validation_dates or not test_dates:
        raise ValueError("chronological split produced an empty validation or test set")
    return (
        frame[frame["date"].isin(train_dates)].copy(),
        frame[frame["date"].isin(validation_dates)].copy(),
        frame[frame["date"].isin(test_dates)].copy(),
    )


def pinball_loss(y_true: np.ndarray, prediction: np.ndarray, alpha: float) -> float:
    error = y_true - prediction
    return float(np.mean(np.maximum(alpha * error, (alpha - 1) * error)))


def _coverage(y_true: np.ndarray, prediction: np.ndarray, alpha: float) -> float:
    return float(np.mean(y_true <= prediction))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def train_quantile_models(
    frame: pd.DataFrame,
    feature_names: list[str],
    output_dir: Path,
    *,
    target: str = "units_sold",
    random_state: int = 42,
    params: dict[str, Any] | None = None,
) -> QuantileTrainingResult:
    try:
        from lightgbm import LGBMRegressor
    except ModuleNotFoundError as exc:
        raise RuntimeError("LightGBM is required to train quantile models") from exc

    frame = validate_training_frame(frame, feature_names, target)
    train, validation, test = chronological_split(frame)
    x_train = train[feature_names].replace([np.inf, -np.inf], np.nan).fillna(0)
    x_validation = validation[feature_names].replace([np.inf, -np.inf], np.nan).fillna(0)
    x_test = test[feature_names].replace([np.inf, -np.inf], np.nan).fillna(0)
    y_train = train[target].to_numpy(dtype=float)
    y_validation = validation[target].to_numpy(dtype=float)
    y_test = test[target].to_numpy(dtype=float)

    common = {
        "n_estimators": 300,
        "learning_rate": 0.05,
        "num_leaves": 31,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "random_state": random_state,
        "verbosity": -1,
    }
    common.update(params or {})
    output_dir.mkdir(parents=True, exist_ok=True)
    models: dict[float, Any] = {}
    predictions: dict[float, np.ndarray] = {}
    metrics: dict[str, Any] = {}

    for alpha in QUANTILES:
        model = LGBMRegressor(objective="quantile", alpha=alpha, **common)
        model.fit(x_train, y_train, eval_set=[(x_validation, y_validation)], callbacks=[])
        path = output_dir / f"demand_p{int(alpha * 100):02d}.pkl"
        import joblib

        joblib.dump(model, path)
        models[alpha] = model
        validation_prediction = model.predict(x_validation)
        test_prediction = model.predict(x_test)
        predictions[alpha] = test_prediction
        metrics[str(alpha)] = {
            "pinball_loss_validation": pinball_loss(y_validation, validation_prediction, alpha),
            "pinball_loss_test": pinball_loss(y_test, test_prediction, alpha),
            "empirical_coverage_test": _coverage(y_test, test_prediction, alpha),
        }

    raw = np.column_stack([predictions[q] for q in QUANTILES])
    crossing_rate = float(np.mean(np.any(np.diff(raw, axis=1) < 0, axis=1)))
    corrected = np.maximum.accumulate(raw, axis=1)
    metrics["interval"] = {
        "nominal_coverage": 0.8,
        "empirical_coverage_test": float(np.mean((y_test >= corrected[:, 0]) & (y_test <= corrected[:, 2]))),
        "mean_width_test": float(np.mean(corrected[:, 2] - corrected[:, 0])),
        "quantile_crossing_rate_raw": crossing_rate,
        "mae_p50_test": float(np.mean(np.abs(y_test - corrected[:, 1]))),
        "rmse_p50_test": float(np.sqrt(np.mean((y_test - corrected[:, 1]) ** 2))),
    }

    manifest = {
        "model_version": "1.0",
        "feature_schema_version": "1.0",
        "model_type": "lightgbm_quantile",
        "feature_names": feature_names,
        "target": target,
        "quantiles": list(QUANTILES),
        "training_start": str(frame["date"].min().date()),
        "training_end": str(frame["date"].max().date()),
        "training_cutoff": str(train["date"].max().date()),
        "validation_start": str(validation["date"].min().date()),
        "test_start": str(test["date"].min().date()),
        "parameters": common,
        "metrics": metrics,
        "models": {},
    }
    for alpha in QUANTILES:
        path = output_dir / f"demand_p{int(alpha * 100):02d}.pkl"
        manifest["models"][str(alpha)] = {
            "filename": path.name,
            "sha256": _sha256(path),
        }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return QuantileTrainingResult(manifest=manifest, metrics=metrics)
