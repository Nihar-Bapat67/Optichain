# Chapter 4 — Machine Learning Pipeline

Only what exists in the code. Missing stages are marked **Not implemented.**

## 4.1 Datasets (all synthetic, all seeded)

| Model | Rows | Shape | Target | Generator |
|---|---|---|---|---|
| M1 baseline | 32,880 → **21,930** after warm-up drop | 30 SKUs × 1096 days (2022-01-01→2024-12-31) | `units_sold` | `model1_script.py:296-331` |
| M2 uplift (notebook) | 10,000 posts (5,482 WS) | 58 influencers × 12 products × 5 tiers | 7 targets | `MODEL2_ML.ipynb` cell 0 |
| M2 uplift (**shipped**) | 3,500 | 18 gaussian `demo_feat_i` + `ws_flag` | 7 targets | `seed_and_train_influencer_demo.py:43` |
| M3 city | 2,700 | 3 cities × 2 categories × 450 days | `extra_units_sold` | `conti_script.py:65-147` |
| LSTM benchmark | 1,096,200 | 600 SKUs × 1827 days | `units_sold` | `MODEL1_LSTM.ipynb` cell 0 |

M1 demand equation (`:310-315`): `base_demand × seasonality × event_effect × dow_mult × yoy_growth × N(1, 0.08)`

## 4.2 Cleaning

| Step | Code | Note |
|---|---|---|
| Sort by (sku_id, date) before lags | `model1_script.py:447` | Prevents corrupt `groupby.shift()` |
| Drop rows where `lag_365` is NaN | `:734` | Costs the entire first year (10,950 rows) |
| `lag_7 ← rolling_7`, `lag_30 ← rolling_30` for residual NaNs | `:739-740` | Impute from the smoothed signal |
| Registry NaN → 0 for West Elm SKUs | `:708-709` | WE has no registry programme |
| Assert zero nulls | `MODEL2_ML.ipynb` cell 1 | Hard fail on generator bugs |
| `replace(±inf, nan).fillna(0)` before predict | `build_case_study_tables.py:63, 195` | Guards division artefacts at scoring time |

No outlier removal, no deduplication, no schema validation. **Not implemented.**

## 4.3 Feature engineering (detail in Chapter 7)

**M1 — 50 features in 7 groups** (`model1_script.py:753-792`)

| Group | Count | Features |
|---|---|---|
| A Lag/rolling | 6 | `lag_7/30/365`, `rolling_7/30`, `trend_ratio_7_30` |
| B Time | 7 | month, day_of_week, week_of_year, quarter, is_weekend, is_q4, day_of_month |
| C Event decay | 22 | 11 events × (`_pre_decay`, `_post_decay`) |
| C′ Days-to | 4 | thanksgiving, christmas, blackfriday, mothersday |
| D Interaction | 3 | `bfcm_overlap`, `holiday_pipeline`, `spring_gifting` |
| E Segment | 5 | ltv_tier_enc, channel_enc, is_gift_buyer, is_registry_buyer, conversion_rate |
| F Registry | 2 | active_registries, items_fulfilled_this_month |
| G Identity | 2 | brand_enc, category_enc |

Decay maths (`:527-539`): `pre = exp(−days_before / (pre_win/4))` for `days_before ≥ 0`; `post = exp(−days_after / (post_win/2))` for `days_after ≥ 1`. Overlapping occurrences combined with `np.maximum` (`:621`), not summed.

**M2 — 95 columns**, 11 engineered (`MODEL2_ML.ipynb` cell 1): `reach_x_er`, `content_relevance`, `inf_content_fit`, `collab_maturity`, `ws_recency_score`, `seasonal_pressure`, `price_norm`, `trust_signal`, `trend_amplifier`, `low_inventory_flag`, `post_timing_score`.

**M3 — 11 features**: day_of_year, month, median_income, median_home_price, affordability_ratio, income_velocity_30d, price_velocity_30d, rolling_units_30d, city_City_B, city_City_C, category_Standard.

## 4.4 Encoding and scaling

| Model | Encoding | Scaling |
|---|---|---|
| M1 | Label/ordinal maps: `brand_map`, `category_map` (`:718-719`), `ltv_map`, `channel_map` (`:681-682`) | **None** — trees are scale-invariant |
| M2 | One-hot on `influencer_tier`, `platform`, `product_category`, `product_id` → 28 dummies | `StandardScaler` on 15 columns saved to `scaler.pkl`, **then excluded from training** (`cell 3`: `not c.endswith("_scaled")`) |
| M3 | `pd.get_dummies(drop_first=True)` → City_A and Luxury are reference levels (`conti_script.py:232`) | **None** |
| LSTM | `get_dummies(drop_first=True)` | `MinMaxScaler` fit on **train only**, target scaled separately for inverse-transform |

⚠ M2's `scaler.pkl` is trained, saved, and never used — dead artefact. Correct decision (trees don't need it), incomplete cleanup.

## 4.5 Embeddings

**Not implemented.** `embedding_similarity` (`MODEL2_ML.ipynb` cell 0) is a synthetic scalar: `0.4·keyword_score + 0.3·hashtag_score + 0.3·U(0.3,0.7)` for WS posts, `U(0.05,0.22)` otherwise. No word2vec, no transformer, no vector store. Captions and hashtags are dropped before training (`cell 1` `DROP_COLS`) after being reduced to three hand-computed scores.

**Never call this NLP in an interview.** Call it "keyword and hashtag overlap scores that stand in for a real text embedding."

## 4.6 Feature selection

**Not implemented.** No RFE, no L1/Lasso selection, no importance-based pruning, no correlation filter, no VIF check. Features are a hand-authored list (`FEATURE_COLUMNS`, `:753-792`); M2 takes everything except targets and `*_scaled`. Two *post-hoc* interpretation tools exist and are frequently mistaken for selection:

- `feature_importance.csv` — gain-based importances written **after** training (`:1070-1073`)
- SHAP on `peak_lift_pct` — computed **after** the winner is refit (`MODEL2_ML.ipynb` cell 3)

Note `valentines_pre_decay` and `valentines_post_decay` have importance exactly **0.0** — two features the model never split on, still shipped.

## 4.7 Training and validation

| | M1 | M2 (notebook) | M3 |
|---|---|---|---|
| Candidates | RandomForest, XGBoost, LightGBM | CatBoost, LightGBM, XGBoost × 7 targets | LightGBM only |
| Validation | Single holdout, time split at **2024-10-01** | `TimeSeriesSplit(n_splits=3)`, OOF | Chronological 80/20 (2160/540) |
| Selection metric | **lowest WMAPE** (`:1050`) | lowest mean OOF RMSE | none (single model) |
| Refit on full data | No | **Yes** after selection | No |
| Winner | XGBoost | CatBoost ×5, XGBoost ×1, LightGBM ×1 | — |

Hyperparameters — XGBoost (`:989-1001`): 500 trees, depth 6, lr 0.05, subsample 0.8, colsample 0.8, min_child_weight 5, α 0.1, λ 1.0. LightGBM M3 (`:254-262`): 700 trees, lr 0.025, depth 10, min_child_samples 10. M2 defaults are deliberately shallow (depth 4, `min_child_weight` 7, λ 3.0) — the notebook says "removed deep tuning to prevent overfitting on small data."

**No hyperparameter search anywhere.** Optuna appears in a `pip install` line (`cell 2`) and is never imported or used. All values are hand-set. **Not implemented:** grid/random/Bayesian search, nested CV, learning curves, early stopping, class/sample weighting in M1.

Only M3 uses sample weights: `1 + 2·(income_velocity_30d > 0.1)` (`conti_script.py:267`) — triples loss weight on surge rows.

## 4.8 Inference

| | Batch | Online |
|---|---|---|
| Trigger | `python scripts/build_case_study_tables.py` | `POST /api/demand/forecast` |
| Models | M1 only | M1 + 7×M2 + M3 = 9 `.predict()` calls |
| Features | Real engineered columns | **Synthesized constants** (`demand_agent.py:46-51`) |
| Output | `analytics/demand_with_predictions.csv` | JSON `ForecastResponse` |

Composition (`:192-193`): `final = baseline + baseline×(peak_lift_pct/100) + city_units`

## 4.9 Post-processing

| Guard | Code |
|---|---|
| `clip(lower=0)` on batch predictions | `build_case_study_tables.py:246` |
| `np.maximum(model.predict(X), 0)` in evaluation | `model1_script.py:1337` |
| `np.clip(preds, 0, 50)` matching the target clamp | `conti_script.py:280` |
| `max(0.0, …)` on final demand | `demand_agent.py:193` |
| `round(…, 2)` on all response floats | `demand_agent.py:192-206` |
| Rolling-mean fallback when pickles are missing | `build_case_study_tables.py:55-62` |

**Not implemented:** integer rounding to whole units, prediction intervals, calibration adjustment at serve time, business-rule overrides.

## 4.10 Evaluation

| Artefact | Content |
|---|---|
| `metrics_overall.json` | WMAPE 16.06, MAPE 14.45, RMSE 32.81, MAE 16.82, R² 0.8823, **bias +0.23**, P90 AE 43.12, n=2760 |
| `model_comparison.csv` | RF 18.91 / **XGB 16.06** / LGBM 17.83 |
| `metrics_by_brand.csv` | PB 15.71, WE 16.25, WS 16.28 |
| `metrics_by_category.csv` | best Cutlery 14.58 → worst Serveware 17.38 |
| `metrics_by_sku.csv` | 30 rows |
| `metrics_by_week.csv` | 6.93 % (quiet Oct) → **27.50 %** (Black Friday week) |
| `event_window_accuracy.csv` | BF window 24.71 vs normal 12.63; **bias −12.02** |
| `calibration.csv` | decile ratios 0.989–1.023 — well calibrated at every volume |
| `residuals.csv` | 2,760 per-row errors |

Metrics defined at `:1295-1318`. WMAPE chosen over MAPE because MAPE explodes on low-volume SKUs and weights a 1-unit SKU like a 300-unit one.

**Not implemented:** naive/seasonal baseline for skill scoring, rolling-origin backtest, confidence intervals, statistical significance tests, business KPI (service level, fill rate, cost of error).

## 4.11 Serialization

| Artefact | Format | Writer |
|---|---|---|
| `ws_model/best_model.pkl` | joblib | `model1_script.py:1234` |
| `ws_model/feature_cols.pkl` | joblib (a `list[str]`) | `:1235` |
| `models/{target}_best.pkl` ×7 | pickle (notebook) / joblib (demo) | `cell 3` / `seed:92` |
| `models/{target}_features.json` ×7 | JSON | `seed:93-94` |
| `models/conti_model.pkl` + `conti_features.json` | joblib + JSON | `conti_script.py:375-377` |
| `scaler.pkl` | pickle — **never loaded** | `cell 1` |
| `ws_lstm_forecaster.keras` | Keras native | `MODEL1_LSTM.ipynb` cell 2 |

Feature lists are always saved alongside the model, and `demand_agent` builds its input frame by iterating that list — so column order is driven by the artefact, not hardcoded. That is the right pattern.

⚠ Pickle couples serving to the training library version (`requirements.txt:11-13` pins ranges). ONNX or a JSON booster dump would decouple them. No model versioning, no hashes, no metadata (train date, data version). **Not implemented.**

## 4.12 Deployment

Frontend → Vercel (`vercel.json`: build `frontend/`, SPA rewrite). Backend → **Not implemented in the current codebase**: no Dockerfile, Procfile, host config, CI, health probes, autoscaling, or model registry. Models load once per process into a module-level dict (`main.py:25-48`); reloading requires a restart.

## 4.13 Error analysis and failure cases

**What the harness found**

1. **Peak-week degradation** — error rises monotonically into Black Friday week (6.93 → 27.50 %), then recovers, then rises again at Christmas/New Year.
2. **Under-forecast bias at events** — BF window bias **−12.02 units/row** while overall bias is +0.23. The model is nearly unbiased on average and badly biased exactly where it matters.
3. **Volume-dependent difficulty** — Furniture has the lowest RMSE (5.55) but the worst WMAPE (17.30 %): low-volume SKUs are proportionally harder.
4. **Calibration is sound** — decile ratios within ±2.3 %, so errors are variance, not systematic mis-scaling.

**Known failure modes**

| Failure | Cause | Impact |
|---|---|---|
| Cold-start SKU | `lag_365` requires a year of history | New products cannot be forecast at all |
| Novel event | Only 11 hardcoded events exist | An unlisted promotion is invisible |
| Serving ≠ training features | `demand_agent.py:46-51` constants | Live accuracy is unmeasured and lower than reported |
| City dummies never fire | `demand_agent.py:112` splits `city_City_B` → `"B"` | Every request scores as City_A |
| Unknown city | 12 of 19 UI cities lack a profile | Identical predictions across those cities |
| Restart changes predictions | `hash()` is salted per process (`:35, :84`) | Non-deterministic service |
| Missing `decay_lambda` model | Unguarded dict access (`:162`) | HTTP 500 |
| Corrupt CSV | Bare `except` returns `None` (`tables.py:16`) | Indistinguishable from a missing file |
| Library version drift | Pickle coupling | Silent load failure → fallback constants with 200 OK |

## 4.14 Key Takeaways

- Three independent supervised regression pipelines; **all data synthetic and seeded**.
- The strongest engineering is anti-leakage (`shift(1).rolling()`), event-decay vectorisation, and a holiday-season test split.
- The weakest link is serving: real features offline, constants online.
- No feature selection, no hyperparameter search, no embeddings, no naive baseline — hand-set everything.
- Evaluation is the standout: 9 artefacts, 8 slices, including bias and decile calibration.

## 4.15 Revision Notes

```
DATA   M1 21,930 rows / 50 feats  ·  M2 10k posts / 95 cols (shipped: 3.5k / 19)
       M3 2,700 rows / 11 feats   ·  LSTM 1,096,200 rows
SPLIT  M1 time holdout 2024-10-01 · M2 TimeSeriesSplit(3) OOF · M3 chrono 80/20
PICK   M1 lowest WMAPE → XGBoost  · M2 lowest OOF RMSE → CatBoost×5, XGB, LGBM
SCALE  none for trees; MinMax for LSTM (train-fit only); M2 scaler saved & unused
POST   clip ≥0 everywhere; conti clip [0,50]; round 2dp
SAVE   joblib .pkl + feature list JSON/pkl beside every model
GAPS   no feature selection · no HPO (Optuna installed, never used) · no embeddings
       · no naive baseline · no intervals · no monitoring · no backend deploy
```

## 4.16 Interview Questions

**Q1. "Walk me through your ML pipeline end to end."**
"Three pipelines. For the baseline: a seeded generator produces 30 SKUs over three years, then feature engineering builds 50 features in seven groups — lags and rollings, calendar, twenty-two event decay columns, three interaction terms, segment, registry, and product identity. I sort by SKU and date first, and rollings are `shift(1).rolling()` so the current day never leaks. I drop the first year because `lag_365` is undefined. Then a time-based split at October 2024, so the test set is the holiday quarter — deliberately the hardest window. Three models trained, XGBoost selected on lowest WMAPE at 16.06 %. Then an evaluation suite writes nine artefacts slicing error by brand, category, SKU, week, event window and prediction decile. The model and its feature list are joblib-dumped together, and an ETL script scores the full history offline so the dashboard reads pre-computed predictions."

**Q2. "Did you do feature selection?"**
"No, and I'd call that a gap rather than a choice. The feature list is hand-authored — fifty columns I designed by domain reasoning. What I have is *post-hoc* importance, which is a different thing: gain-based importances written after training, and SHAP for `peak_lift_pct` in the influencer notebook. The evidence that selection would help is in my own output — `valentines_pre_decay` and `valentines_post_decay` have importance exactly zero, so the model never split on them. If I extended this I'd try recursive feature elimination with the time-series CV I already use for Model 2, and check whether the twenty-two event columns can collapse into fewer aggregate signals, since `holiday_pipeline` — which is a normalised sum of three of them — already outranks all but two individual features."

**Q3. "You mention embeddings — what embedding model did you use?"**
"None, and I want to be precise about that because the column name is misleading. `embedding_similarity` is a synthetic scalar in my data generator: a weighted blend of keyword overlap, hashtag overlap and a uniform random term. There is no word2vec, no transformer, no vector database. The captions and hashtags are reduced to three hand-computed overlap scores and then dropped before training. If I were making it real I'd encode caption and product description with a sentence-transformer and use cosine similarity — that's the natural upgrade, and `content_relevance` is already shaped as the right feature to replace."

**Q4. "How did you tune hyperparameters?"**
"I didn't — they're hand-set, and that's the honest answer. Optuna appears in one `pip install` line in the notebook and is never imported. For Model 2 the defaults are deliberately conservative — depth 4, high `min_child_weight`, L2 of 3.0 — because with ten thousand rows and eighty features the risk was overfitting, not underfitting. Model 3 is the opposite and probably wrong: 700 trees at depth 10 on 2,160 training rows, and LightGBM logs 'no further splits with positive gain' repeatedly, which is the model telling me it's over-parameterised. The right next step is a proper search with the TimeSeriesSplit I already use, optimising WMAPE rather than RMSE so tuning matches selection."

**Common mistakes:** calling `embedding_similarity` an embedding; presenting SHAP as feature selection; quoting the notebook's M2 metrics as the deployed model's; claiming hyperparameters were tuned; omitting that the target is a known generator.

---
**End of Chapter 4.** Type **Continue** for Chapter 5 — ML Theory Connected to My Code.
