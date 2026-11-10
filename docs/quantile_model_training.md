# Quantile model training

Run from the repository root after installing `backend/requirements.txt`:

```powershell
python scripts\train_quantile_models.py
```

The command reads `ws_demand_dataset/ml_ready_data.csv` and the existing
`ws_model/feature_cols.pkl` schema. It validates required columns, duplicate
SKU/date keys, finite targets and chronological ordering. Dates are split into
train, validation and test periods; random time-series splits are not used.

Three independent `LGBMRegressor` models are trained with
`objective="quantile"` and alphas 0.10, 0.50 and 0.90. The script writes
`demand_p10.pkl`, `demand_p50.pkl`, `demand_p90.pkl` and `manifest.json`.
Training never runs during API startup or a request.

The manifest includes the feature names, target, date boundaries, parameters,
pinball losses, empirical coverages, interval coverage, interval width, P50
MAE/RMSE and raw quantile crossing rate. Predictions are not rounded during
training or inference.
