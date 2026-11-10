# Probabilistic forecasting architecture

Optichain keeps the existing composite point forecast and adds an optional daily
quantile path. The existing XGBoost baseline, influencer uplift bundle and
Conti city-growth model still produce `final_demand`. Separately, three
LightGBM models estimate conditional demand quantiles at alpha 0.10, 0.50 and
0.90. The serving layer exposes these as optional `quantiles`, `interval` and
`model_metadata` fields.

Quantile artifacts are trained by `scripts/train_quantile_models.py`, stored
independently under `quantile_models/`, and loaded once during FastAPI lifespan
startup. A manifest records the shared feature schema, training dates,
parameters, metrics and SHA-256 checksums. The loader rejects an incomplete,
corrupt or incompatible set, while the point forecast continues to work.

The current dataset is a daily `units_sold` target. Quantile outputs are
therefore daily conditional estimates. They are not summed to claim a
cumulative P90 or an exact stockout probability. The risk endpoint uses them as
an explicitly labeled daily threshold context until a direct cumulative target
or calibrated dependent scenarios are available.

P10/P50/P90 are estimates, not automatic coverage guarantees. Empirical
coverage, interval width and crossing rate are recorded by the training
pipeline.
