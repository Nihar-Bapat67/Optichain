# Probabilistic forecasting edge cases

The edge-case suite is organized into ten categories of twenty case IDs:

| Category | IDs | Scope |
|---|---:|---|
| A | E001-E020 | Ingestion and schema |
| B | E021-E040 | Time series and leakage |
| C | E041-E060 | SKU and sparse data |
| D | E061-E080 | Numeric distributions and outliers |
| E | E081-E100 | Model training |
| F | E101-E120 | Quantile calibration |
| G | E121-E140 | Aggregation and inventory risk |
| H | E141-E160 | API and PostgreSQL |
| I | E161-E180 | Frontend and visualization |
| J | E181-E200 | Deployment and production readiness |

The executable manifest is maintained alongside the pytest cases. Each case
must assert a meaningful accepted result or explicit validation/error outcome.
Infrastructure failures use mocks; database tests use an isolated PostgreSQL
database when available. Synthetic transformations of repository data are
labeled synthetic and are never reported as real-world validation.

Important safety expectations include no target leakage, no random split for
time series, no P50 relabeling of the old point forecast, no exact probability
claim from P90 alone, no fabricated density from three quantiles, and no
destructive production migration.
