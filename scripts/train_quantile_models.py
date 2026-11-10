"""Train daily P10/P50/P90 demand models outside the FastAPI process."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings
from app.services.quantile_training import train_quantile_models


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=settings.ml_ready_path())
    parser.add_argument("--output", type=Path, default=settings.quantile_model_dir_path())
    args = parser.parse_args()

    frame = pd.read_csv(args.input, parse_dates=["date"])
    features = list(joblib.load(settings.feature_cols_path()))
    result = train_quantile_models(frame, features, args.output)
    print(result.manifest["metrics"])


if __name__ == "__main__":
    main()
