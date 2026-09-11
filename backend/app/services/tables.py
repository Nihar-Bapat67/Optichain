from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _read_csv(path: Path, **kwargs: Any) -> pd.DataFrame | None:
    """Read a CSV, returning None when it is missing or unreadable.

    The None return is unchanged, but a corrupt file is now logged rather than
    being indistinguishable from an absent one.
    """
    if not path.is_file():
        logger.debug("CSV not found: %s", path)
        return None
    try:
        return pd.read_csv(path, **kwargs)
    except Exception:
        logger.exception("Failed to read CSV: %s", path)
        return None


def load_demand_predictions() -> pd.DataFrame | None:
    return _read_csv(settings.demand_predictions_path(), parse_dates=["date"])


def load_sales_fallback() -> pd.DataFrame | None:
    """If analytics missing, use ml_ready with units_sold only (no predictions)."""
    df = _read_csv(settings.ml_ready_path(), parse_dates=["date"])
    if df is None:
        return None
    if "predicted_units" not in df.columns:
        df = df.copy()
        df["predicted_units"] = float("nan")
    return df


def load_inventory() -> pd.DataFrame | None:
    return _read_csv(settings.inventory_path())


def load_signals() -> pd.DataFrame | None:
    return _read_csv(settings.signals_path(), parse_dates=["date"])


def load_influencer_sample() -> pd.DataFrame | None:
    return _read_csv(settings.influencer_sample_path())


def load_influencer_metrics() -> dict | None:
    path = settings.influencer_metrics_path()
    if not path.is_file():
        logger.debug("Influencer metrics not found: %s", path)
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.exception("Failed to read influencer metrics: %s", path)
        return None
