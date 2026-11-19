# Data Pipeline Faults and Bugs

This is an implementation handoff for refactoring the data and ML pipeline.
The findings below are based on the current code, not assumptions. Each item
includes the observed behavior, an example, impact, and a suggested starting
point.

## Executive summary

The project is a functional prototype with a database-backed serving layer,
but the database is not yet the source of truth for model training. The
current flow is:

```text
CSV files and synthetic generators
        |
        v
Training scripts create pickle artifacts
        |
        v
Case-study scripts create more CSV files
        |
        v
Ingest replaces database tables from CSV files
        |
        v
FastAPI serves database data and model artifacts
```

The target flow should be:

```text
Monthly upload
        |
        v
Immutable ingestion batch and raw tables
        |
        v
Validated curated tables
        |
        v
Reusable feature generation
        |
        v
Versioned training dataset
        |
        v
Candidate training and evaluation
        |
        v
Model registry and promotion gate
        |
        v
Versioned forecasts and monitoring
```

## 1. Training does not use the database

### Observed behavior

The three main model-training paths read files or generate data directly.
They do not query the SQLAlchemy database.

#### Model 1: baseline demand

[`scripts/model1_script.py`](../scripts/model1_script.py) loads the training
frame directly from `ws_demand_dataset/ml_ready_data.csv` at lines 899-911:

```python
DATA_DIR = "ws_demand_dataset"
df = pd.read_csv(f"{DATA_DIR}/ml_ready_data.csv", parse_dates=["date"])
```

Its feature engineering is also file-based. The script calculates grouped
lags and rolling features at lines 458-474, writes the resulting training
frame to `ml_ready_data.csv` at line 803, and later trains from that file.

The database table containing similar columns is
[`backend/app/db/schema.py`](../backend/app/db/schema.py). It is not read by
the Model 1 training script.

#### Model 2: influencer uplift

[`scripts/seed_and_train_influencer_demo.py`](../scripts/seed_and_train_influencer_demo.py)
creates a new synthetic dataframe in `_synthetic_frame()` at lines 43-70:

```python
X = RNG.normal(0, 1, (n, N_FEAT))
df["ws_flag"] = RNG.integers(0, 2, size=n)
```

It trains seven target models from this generated dataframe and writes pickle
artifacts at lines 85-93. The data is not loaded from `influencer_sample` or
any other database table.

#### Model 3: city/economic uplift

[`scripts/conti_script.py`](../scripts/conti_script.py) generates the city
profiles and economic series in memory. For example, it defines three cities
at line 10 and builds synthetic income and price series before constructing
the training rows.

Later parts of the script read `luxury_surge_dataset.csv` at lines 174 and
224. They still do not query the database.

#### Quantile demand models

The newer quantile pipeline also reads a CSV. In
[`scripts/train_quantile_models.py`](../scripts/train_quantile_models.py)
lines 22-27, the script reads `settings.ml_ready_path()` with
`pd.read_csv()` and loads the feature list from a pickle file.

### Example of the current problem

Suppose a new monthly sales upload is successfully ingested into
`demand_daily`. Running Model 1 afterward will not automatically use those
rows. It will continue using the existing `ml_ready_data.csv` until another
script regenerates that file and the training command is pointed at it.

### Impact

- The database is not the training source of truth.
- A database correction may not affect the next model.
- Training and serving can use different versions of the data.
- Data lineage cannot reliably answer which database batch trained a model.
- Monthly retraining cannot be driven from database state alone.

### Suggested starting point

Create a training-data repository or export job that reads validated database
tables and returns a typed dataframe. Then change each training entry point to
accept that frame or a database connection rather than hardcoded CSV paths.
Do not delete the CSV path immediately; first add a comparison test proving
that database export and the current training frame have the same schema,
ordering, row count, and values.

An initial implementation now exists in
[`backend/app/db/training.py`](../backend/app/db/training.py). It provides
deterministic database loaders for demand, influencer, and city/economic
tables. Model 1 and Model 3 can use the database loader with
`OPTICHAIN_TRAINING_SOURCE=database`, `seed_and_train_influencer_demo.py`
accepts `--source database`, and quantile training accepts `--source database`.

The city/economic source table is now `city_economic_daily`; ingestion validates
its date/city/category key and numeric target columns before loading it. The
database source path in `scripts/conti_script.py` also avoids rewriting the
source CSV.

## 2. Ingest fully replaces the database

### Observed behavior

[`backend/app/db/ingest.py`](../backend/app/db/ingest.py) validates sources and
builds rows, but `ingest()` deletes all owned tables at lines 364-380:

```python
for table in reversed(schema.DATA_TABLES):
    conn.execute(table.delete())
conn.execute(schema.dataset_meta.delete())
```

It then inserts the current source contents and creates one `ingest_runs`
record. The transaction and `verify_loaded()` call are good safeguards against
partial or corrupted writes, but they do not preserve prior data.

The owned table list is defined in
[`backend/app/db/schema.py`](../backend/app/db/schema.py) as
`DATA_TABLES = [skus, demand_daily, inventory, signals, influencer_sample,
documents]`.

### Example of the problem

Assume the database contains January through October. A November CSV
containing only November rows is uploaded. A full replacement implementation
will leave the database containing only November rows unless the source file
itself contains January through November.

If a malformed full-history file omits one SKU, the ingest can remove that SKU
from the serving database after validation succeeds for the remaining rows.

### Impact

- Monthly incremental uploads are not naturally supported.
- Historical data can disappear from the serving database.
- A source correction requires rebuilding the entire table.
- The database cannot provide a reliable historical snapshot per upload.
- Concurrent consumers see the new version only after commit, but the new
  version may still represent an unintended replacement.

### Suggested starting point

Introduce an `ingestion_batches` table and immutable raw tables first. Give
each batch a source checksum, received timestamp, period, and validation
status. Load new rows with stable business keys and use explicit upsert or
duplicate-rejection behavior.

An initial compatibility step now exists in
[`backend/app/db/ingest.py`](../backend/app/db/ingest.py) through the explicit
`mode="incremental"` path at lines 364-407 and the `--incremental` CLI option
at line 573. It preserves older demand and signal rows, replaces incoming
SKU/date or signal keys idempotently, and refreshes inventory and influencer
tables only when a complete snapshot is supplied. The existing replacement
mode remains available for current fixtures and startup compatibility.

This is not yet a complete raw-table design: monthly rows are still loaded
from the configured source files, and `dataset_loads` currently records load
history rather than preserving every raw row. The next step is to introduce
immutable raw tables and an explicit batch-period contract before removing or
restricting replacement mode.

## 3. Facts, features, and predictions are mixed together

### Observed behavior

[`backend/app/db/schema.py`](../backend/app/db/schema.py) defines
`demand_daily` with all of the following in one table:

- identity: `sku_id`, `date`;
- engineered features: `lag_7`, `lag_30`, `lag_365`, `rolling_7`,
  `rolling_30`, and many calendar/event columns;
- observed target: `units_sold`;
- model output: nullable `predicted_units` at line 120.

The ingest code explicitly copies `predicted_units` from the source at
[`backend/app/db/ingest.py`](../backend/app/db/ingest.py) lines 230 and
297-307.

The read repository also exposes observed and predicted values together in
`demand_core()` at [`backend/app/db/repository.py`](../backend/app/db/repository.py)
lines 160-172.

### Example of the problem

One row currently conceptually means:

```text
SKU-1, 2026-01-15,
lag_7=80,
rolling_30=92,
units_sold=100,
predicted_units=97
```

But these values have different meanings:

- `units_sold` is an observed fact;
- `lag_7` and `rolling_30` are derived features produced by a feature version;
- `predicted_units` is an output from a particular model version and scoring
  run.

If the model is retrained, `predicted_units` may need to be regenerated while
the observed sales and feature history remain unchanged.

### Impact

- Recomputing features can unintentionally overwrite predictions.
- Comparing predictions from different model versions is difficult.
- Historical predictions lose their model identity.
- Training data cannot be cleanly separated from scoring outputs.
- Feature freshness and prediction freshness cannot be tracked separately.

### Suggested starting point

Split the logical data into:

```text
sales_daily
features_daily
forecasts
```

Use keys such as:

```text
sales_daily:    sku_id, warehouse_id, sales_date
features_daily: sku_id, feature_date, feature_schema_version
forecasts:      sku_id, forecast_date, model_version, generated_at
```

Keep `units_sold` immutable after validation except through an explicit
correction workflow.

## 4. Online feature generation can differ from training

### Observed behavior

The batch Model 1 path trains on columns created by
[`scripts/model1_script.py`](../scripts/model1_script.py) and stored in
`ml_ready_data.csv`.

The online agent can instead call `_synthesize_m1_features()` in
[`backend/app/services/demand_agent.py`](../backend/app/services/demand_agent.py)
at line 34. The agent calls it for Model 1 inputs at line 169.

The quantile serving path has the same fallback behavior. In
[`backend/app/services/quantile_forecast.py`](../backend/app/services/quantile_forecast.py)
lines 25-46, it uses stored features only when every required feature is
available; otherwise it calls `_synthesize_m1_features()`.

The database does expose an exact row lookup through
`DataStore.feature_row()` at
[`backend/app/db/repository.py`](../backend/app/db/repository.py) lines
200-206. The existence of that helper does not guarantee that every forecast
path uses it.

### Example of the problem

Offline training may use:

```text
lag_7 = actual sales from seven prior days
rolling_30 = prior 30-day average
```

An online request for a future date may not have a stored feature row and can
receive synthesized/default values instead. The model then receives a vector
with the correct column names but a different data-generating process.

### Impact

- Offline accuracy is not a reliable estimate of online accuracy.
- Forecasts can be systematically wrong for real SKU/date requests.
- Debugging is difficult because the feature vector is not persisted with the
  prediction.
- Retraining can improve offline metrics while production behavior worsens.

### Suggested starting point

Create one canonical feature builder used by both training and serving. For
each prediction, persist the feature schema version and either the feature
row or a reproducible feature snapshot reference. If a feature row is
unavailable, return an explicit cold-start status or use a documented fallback
model rather than silently presenting a normal forecast.

## 5. Model artifacts lack one consistent registry

### Observed behavior

Legacy artifact loading is file-based. For example,
[`backend/app/services/artifacts.py`](../backend/app/services/artifacts.py)
loads Model 1 with `joblib.load()` at lines 27-45 and loads Model 2 artifacts
at lines 59-86.

Model 1 saves a model and feature list as separate pickle files at
[`scripts/model1_script.py`](../scripts/model1_script.py) lines 1234-1235.
Model 2 saves separate target pickles and feature JSON files at
[`scripts/seed_and_train_influencer_demo.py`](../scripts/seed_and_train_influencer_demo.py)
lines 92-93.

The quantile pipeline is better: it writes a manifest containing feature names,
training dates, parameters, metrics, and artifact hashes in
[`backend/app/services/quantile_training.py`](../backend/app/services/quantile_training.py)
lines 139-161. However, that manifest is not a registry for all model families.

### Example of the problem

The API can load `ws_model/best_model.pkl`, but there is no single database
record saying:

```text
model_version: demand-2026-11-01-003
training_batch: monthly-2026-10
feature_schema: demand-features-v4
status: production
approved_by: ...
```

Replacing a pickle on disk is therefore not the same as an auditable model
deployment.

### Impact

- Rollback depends on filesystem copies.
- Predictions cannot reliably identify the exact model artifact.
- Training data and feature schema lineage are incomplete.
- Multiple processes may load different files during deployment.
- Library/version incompatibility can break artifact loading.

### Suggested starting point

Add a `model_versions` table or registry service with immutable model records.
Store the artifact URI, checksum, model type, feature schema version, training
cutoff, metrics, and lifecycle status. Make the API load the explicitly
active version instead of an implicit filename.

The schema and first registry service now exist:

- `model_versions` stores artifact identity, hashes, feature schema, cutoff,
  metrics, and lifecycle status.
- `training_runs` records candidate training execution metadata.
- `backend/app/services/model_registry.py` supports registration, promotion,
  retirement of the previous production version, and active-version lookup.

The API artifact loader still uses legacy filesystem paths, so the next
integration step is changing startup loading to resolve the active registry
version and verify its checksum before serving.

## 6. Synthetic data is used for shipped model training

### Observed behavior

Model 2's demo training frame is generated with random features and generated
targets in `_synthetic_frame()` at
[`scripts/seed_and_train_influencer_demo.py`](../scripts/seed_and_train_influencer_demo.py)
lines 43-70. The resulting models are written as normal serving artifacts.

Model 3 generates synthetic city/economic time series in
[`scripts/conti_script.py`](../scripts/conti_script.py) before training.

### Example of the problem

A model can achieve a good metric on a generated relationship because the
training and test data share the same synthetic equation. That does not show
that the model predicts actual influencer lift or actual city demand.

### Impact

- Reported metrics do not represent production accuracy.
- Synthetic relationships can hide missing real-world variables.
- The model may fail on real SKU, campaign, or city distributions.
- Stakeholders may interpret demo artifacts as production-certified models.

### Suggested starting point

Label generated datasets and artifacts explicitly as `demo` or `synthetic`.
Define production data contracts for real sales, influencer, and economic
inputs. Do not promote a synthetic-trained artifact to production without a
separate validation dataset from the real operating environment.

## 7. No monthly ingestion and retraining workflow exists

### Observed behavior

The repository has independent scripts for feature generation, model training,
case-study table construction, and database ingest. The startup path can also
initialize or refresh the database through `ensure_database()` in
[`backend/app/db/ingest.py`](../backend/app/db/ingest.py), but that is not a
monthly ML workflow.

The current scripts do not form one tracked job with a shared batch ID,
training cutoff, candidate model, approval result, and published forecast.

### Example of the desired monthly run

```text
1. Receive 2026-11 sales and inventory files
2. Validate schema, keys, dates, and numeric ranges
3. Store batch as accepted
4. Append/upsert curated records
5. Rebuild features through 2026-11-30
6. Train candidate model using data through the cutoff
7. Evaluate candidate against the champion
8. Promote only if quality gates pass
9. Generate December forecasts
10. Record the run and publish metrics
```

### Impact

- Operators must run scripts manually in the correct order.
- Partial completion is difficult to detect.
- A model can be trained on stale or incomplete data.
- There is no single run record for audit or retry.

### Suggested starting point

Implement an orchestration command or job with explicit stages and persisted
status. Each stage should be idempotent and record its input batch, output
artifact, row counts, and failure reason. Start with a command-line workflow
before adding a scheduler.

## 8. No champion-versus-candidate promotion gate

### Observed behavior

Training scripts save selected models and metrics, but there is no general
promotion service comparing a candidate with the currently deployed model.
Model 1 selects among local algorithms in
[`scripts/model1_script.py`](../scripts/model1_script.py) around lines
1047-1051, but that is algorithm selection within one training run, not
production promotion.

### Example of the difference

Current behavior:

```text
Candidate XGBoost wins against RandomForest and LightGBM
-> save XGBoost artifact
```

Required production behavior:

```text
Candidate XGBoost
-> compare against current production model on the same holdout
-> check error, bias, SKU coverage, and business thresholds
-> promote or reject
```

### Impact

- A new model can replace a better production model.
- Small or unrepresentative validation gains can trigger deployment.
- There is no automatic rollback decision.

### Suggested starting point

Define quality gates such as:

```text
candidate WMAPE <= champion WMAPE
candidate bias within allowed range
candidate has no severe SKU/category regression
candidate passes schema and artifact validation
```

Store the decision and both model versions in the model registry.

## 9. Limited production monitoring

### Observed behavior

The repository contains offline evaluation outputs and risk calculations, but
there is no complete closed-loop process that joins future actuals to the
forecasts that produced them.

The risk path reads `predicted_units` from the combined demand table in
[`backend/app/api/routes/risk.py`](../backend/app/api/routes/risk.py) lines
105-111. Because predictions do not have a model-versioned forecast table,
this is not sufficient for durable post-deployment evaluation.

The API health path reports whether artifacts loaded, but artifact availability
is different from model quality monitoring.

### Example of missing monitoring

After November actuals arrive, the system should be able to calculate:

```text
forecast generated on 2026-10-31
model version demand-2026-10-01-002
SKU-1, forecast date 2026-11-05, p50=100, actual=145
```

and aggregate error by SKU, category, event period, warehouse, and horizon.
The current combined table does not preserve enough identity for this
reliably.

### Impact

- Model degradation can remain hidden.
- Event-period failures may be diluted by average metrics.
- Inventory decisions may continue using a degraded model.
- Data-quality failures may be mistaken for demand changes.

### Suggested starting point

Create versioned forecast records and a delayed evaluation job. Track:

- WMAPE, MAE, RMSE, and bias;
- coverage and interval width for quantile forecasts;
- error by SKU, category, warehouse, and event window;
- feature and target drift;
- stockout, service-level, and fill-rate outcomes.

## 10. Important existing schema fact: SKU-wise features do exist

This is not a fault. It is an important fact for the refactor.

[`backend/app/db/schema.py`](../backend/app/db/schema.py) defines the primary
key of `demand_daily` as `(sku_id, date)` and includes `lag_7`, `lag_30`,
`lag_365`, `rolling_7`, and `rolling_30` at lines 30 and 75-120.

The Model 1 feature builder groups rows by SKU and calculates lags/rollings in
[`scripts/model1_script.py`](../scripts/model1_script.py) at lines 458-474.
Therefore, the batch data is SKU-wise.

The actual problems are:

1. training reads the CSV instead of the database;
2. serving can synthesize features instead of using the exact stored row;
3. facts, features, and predictions are stored together;
4. feature version and prediction model version are not consistently recorded.

## Recommended implementation order

### Phase 1: make data ownership explicit

1. Add ingestion batch metadata.
2. Preserve raw uploads.
3. Add append/upsert semantics.
4. Keep current replacement ingest only for development fixtures.

### Phase 2: separate data products

1. Split observed sales from features.
2. Split forecasts from both.
3. Add model version and feature schema to every forecast.

### Phase 3: unify training and serving features

1. Extract the canonical feature builder.
2. Use it for database training exports.
3. Use it for online scoring.
4. Add cold-start behavior explicitly.

### Phase 4: add model lifecycle management

1. Register candidate artifacts.
2. Validate checksums and schemas.
3. Compare candidates with the champion.
4. Promote atomically.
5. Support rollback.

### Phase 5: automate and monitor

1. Orchestrate the monthly workflow.
2. Persist each stage's status.
3. Join forecasts to later actuals.
4. Publish drift and business metrics.

The safest first production retraining strategy is full retraining on all
validated history through a cutoff date. Incremental or online learning should
only be introduced after the batch process is reproducible and monitored.

The first reproducible orchestration command is now
[`scripts/monthly_pipeline.py`](../scripts/monthly_pipeline.py). It runs
incremental ingest followed by database-backed Model 1, Model 2, Model 3, and
quantile training. Use `--skip-training` when only the monthly data load is
required.
