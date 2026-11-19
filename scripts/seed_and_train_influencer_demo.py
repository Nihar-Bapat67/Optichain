#!/usr/bin/env python3
"""
Train a minimal MODEL2-style bundle for local demo when notebook outputs are missing.

Writes:
  - features_engineered.csv (repo root)
  - models/{target}_best.pkl + models/{target}_features.json for all seven targets

Uses sklearn only (no CatBoost) so backend loads without extra pip installs.

For production, replace artifacts with outputs from MODEL2_ML.ipynb.
"""

from __future__ import annotations

import json
import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models"

TARGETS = [
    "lift_6h",
    "lift_24h",
    "lift_48h",
    "lift_72h",
    "lift_96h",
    "peak_lift_pct",
    "decay_lambda",
]

N_ROWS = 3500
N_FEAT = 18
RNG = np.random.default_rng(42)


def _synthetic_frame() -> pd.DataFrame:
    n = N_ROWS
    X = RNG.normal(0, 1, (n, N_FEAT))
    feat_names = [f"demo_feat_{i}" for i in range(N_FEAT)]
    df = pd.DataFrame(X, columns=feat_names)
    df["ws_flag"] = RNG.integers(0, 2, size=n)

    # Correlated "lift" surfaces (positive, smooth) so GBDT learns non-trivial fit
    z = (
        0.4 * X[:, 0]
        + 0.35 * X[:, 1]
        + 0.2 * X[:, 2]
        + 0.15 * X[:, 3] * X[:, 4]
        + 0.05 * df["ws_flag"].values
    )
    base = np.exp(0.35 * z) * 80 + 20

    df["lift_6h"] = np.clip(base * (0.35 + 0.08 * RNG.normal(0, 1, n)), 5, None)
    df["lift_24h"] = np.clip(df["lift_6h"] * (1.6 + 0.1 * RNG.normal(0, 1, n)), 10, None)
    df["lift_48h"] = np.clip(df["lift_24h"] * (1.25 + 0.08 * RNG.normal(0, 1, n)), 15, None)
    df["lift_72h"] = np.clip(df["lift_48h"] * (1.12 + 0.06 * RNG.normal(0, 1, n)), 20, None)
    df["lift_96h"] = np.clip(df["lift_72h"] * (1.08 + 0.05 * RNG.normal(0, 1, n)), 25, None)
    df["peak_lift_pct"] = np.clip(8 + 22 * (1 / (1 + np.exp(-z))) + 3 * RNG.normal(0, 1, n), 0.5, 95)
    df["decay_lambda"] = np.clip(
        0.12 + 0.35 * (1 / (1 + np.exp(-0.8 * z))) + 0.05 * RNG.normal(0, 1, n), 0.05, 0.95
    )

    return df


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("synthetic", "database"), default="synthetic")
    args = parser.parse_args()

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    if args.source == "database":
        sys.path.insert(0, str(ROOT / "backend"))
        from app.db.engine import get_engine
        from app.db.migrations import run_migrations
        from app.db.training import load_influencer_training_frame

        engine = get_engine()
        run_migrations(engine)
        df = load_influencer_training_frame(engine)
        print(f"[ok] Loaded influencer training data from database ({len(df)} rows)")
    else:
        df = _synthetic_frame()
        print(f"[ok] Generated synthetic influencer training data ({len(df)} rows)")
    feat_cols = [c for c in df.columns if c not in TARGETS]

    out_csv = ROOT / "features_engineered.csv"
    df.to_csv(out_csv, index=False)
    print(f"[ok] Wrote {out_csv} ({len(df)} rows × {len(df.columns)} cols)")

    for t in TARGETS:
        y = df[t].values
        X = df[feat_cols].replace([np.inf, -np.inf], np.nan).fillna(0)
        model = HistGradientBoostingRegressor(
            max_depth=5,
            max_iter=120,
            learning_rate=0.08,
            random_state=42,
        )
        model.fit(X, y)
        joblib.dump(model, MODEL_DIR / f"{t}_best.pkl")
        with open(MODEL_DIR / f"{t}_features.json", "w", encoding="utf-8") as f:
            json.dump(feat_cols, f)
        print(f"[ok] Trained & saved {t} ({len(feat_cols)} features)")

    print("[done] Restart the FastAPI server to load MODEL2 into memory.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
