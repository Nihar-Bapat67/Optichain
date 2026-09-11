"""Shared helpers for route modules."""

from __future__ import annotations

import pandas as pd

from app.services import tables


def demand_frame() -> pd.DataFrame | None:
    """Predictions table when available, otherwise the raw sales fallback.

    Behaviour is identical to the previous `_demand_frame()` in main.py.
    """
    df = tables.load_demand_predictions()
    if df is not None:
        return df
    return tables.load_sales_fallback()
