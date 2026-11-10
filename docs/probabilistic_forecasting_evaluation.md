# Probabilistic forecasting evaluation

The evaluation reports nominal and empirical values separately:

- Pinball loss for each quantile.
- P10, P50 and P90 empirical coverage.
- Nominal P10/P90 interval coverage versus observed test coverage.
- Mean P10-P90 interval width.
- Raw quantile crossing rate.
- P50 MAE and RMSE.

Evaluation is chronological and uses multiple dates and all available SKUs in
the validation/test periods. A P10/P90 interval is not called calibrated
unless its observed coverage is measured. The served values are monotonically
corrected with a documented cumulative maximum when independent models cross;
the raw crossing rate remains in the manifest for diagnosis.

The current data source contains the project model-ready sales dataset and is
not represented as external real-world validation. If a separate production
historical dataset is unavailable, that limitation must be included in release
reports.
