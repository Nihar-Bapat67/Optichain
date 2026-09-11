# Chapters 5–13 — Theory, Analysis, Performance, Interview Prep

---

# Chapter 5 — ML Theory Connected to My Code

## 5.1 Every model here is a gradient-boosted decision tree

Boosting builds an additive model, one tree at a time, each fitting the previous model's errors:

```
F₀(x) = mean(y)
Fₘ(x) = Fₘ₋₁(x) + ν · hₘ(x)          ν = learning_rate (0.05 in my XGBoost)
hₘ fits the negative gradient of the loss w.r.t. Fₘ₋₁
For squared loss:  −∂L/∂F = (y − F)  → each tree fits the residual
```

With `n_estimators=500, learning_rate=0.05` (`model1_script.py:989-1001`), no single tree matters much — 500 small corrections of 5 % each. Lower `lr` + more trees = better generalisation at higher training cost. That is the central boosting trade-off and my values sit on the conservative side of it.

## 5.2 XGBoost — why it won MODEL1

XGBoost uses a **second-order** Taylor expansion of the loss plus an explicit complexity penalty:

```
Obj = Σᵢ [ gᵢ·f(xᵢ) + ½·hᵢ·f(xᵢ)² ] + Ω(f)        Ω(f) = γT + ½λ‖w‖²
optimal leaf weight   w*ⱼ = − Gⱼ / (Hⱼ + λ)
split gain            ½[ G²_L/(H_L+λ) + G²_R/(H_R+λ) − G²/(H+λ) ] − γ
```

`G`, `H` = sums of first and second derivatives in a leaf. Mapping to my hyperparameters:

| Param | Value | Theory |
|---|---|---|
| `reg_lambda` | 1.0 | the λ in `w* = −G/(H+λ)` — shrinks leaf weights |
| `reg_alpha` | 0.1 | L1 on leaf weights — drives some to exactly 0 |
| `min_child_weight` | 5 | minimum Σh in a leaf; for squared loss h=1, so ≥5 rows per leaf |
| `max_depth` | 6 | ≤ 2⁶ = 64 leaves per tree |
| `subsample` | 0.8 | row sampling → variance reduction, like bagging inside boosting |
| `colsample_bytree` | 0.8 | column sampling → decorrelates trees; matters with 22 correlated decay columns |

**Why it beat LightGBM here (16.06 vs 17.83 WMAPE):** with only ~22k rows and 50 features, LightGBM's leaf-wise growth (`num_leaves=63`, depth 8) can chase noise down deep narrow branches. XGBoost's level-wise growth at depth 6 is more conservative. LightGBM's speed advantage needs scale I don't have.

## 5.3 LightGBM — why it won MODEL3 (and `decay_lambda`)

Leaf-wise growth (split the leaf with max delta-loss, not every leaf), histogram binning of continuous features, GOSS (keep large-gradient rows, subsample small-gradient ones), and EFB (bundle mutually-exclusive sparse features). `conti_script.py:254-262`: 700 trees, lr 0.025, depth 10, `min_child_samples=10`.

⚠ **That is over-parameterised for 2,160 training rows** and the saved notebook output proves it — LightGBM prints `No further splits with positive gain` repeatedly. Say this before you're asked.

The one genuinely sophisticated choice in MODEL3 is **sample weighting** (`:267`):

```python
sample_weights = 1 + (X_train["income_velocity_30d"] > 0.1) * 2   # weight 3 on surge rows
```

This reweights the empirical loss so the ~10 % of surge rows contribute ~25 % of it. It is exactly the fix MODEL1 needs for its Black Friday under-forecast — you already used the technique once, in a different model.

## 5.4 CatBoost — why it won 5 of 7 MODEL2 targets

Two mechanisms, both aimed at small-data overfitting:
- **Ordered boosting** — each row's residual is computed by a model trained only on rows preceding it, eliminating the target leakage that ordinary boosting has when the same row informs its own gradient.
- **Oblivious (symmetric) trees** — the same split condition at every node of a level. Far fewer degrees of freedom = strong implicit regularisation, and vectorised inference.

With 5,482 WS rows and 80 features, that regularisation won. It also **lost** `peak_lift_pct` to XGBoost (11.6183 vs 11.7012) — when the target has enough signal, the extra flexibility pays.

## 5.5 Random Forest — why it lost (18.91 WMAPE)

Bagging reduces **variance** by averaging decorrelated trees; boosting reduces **bias** by sequentially correcting errors. My target is a sharp multiplicative spike function — Christmas is a 2.5× multiplier on top of a 35-day exponential ramp. Averaging 200 trees at `max_depth=12, min_samples_leaf=5` smooths those peaks; boosting keeps adding trees until the residual at the peak is small. Predicting *sharp, rare, high-magnitude* structure is a bias problem, and boosting is the bias-reduction algorithm.

## 5.6 LSTM — why it lost badly (45.81 vs 16.06 WMAPE)

Architecture (`MODEL1_LSTM.ipynb` cell 2): `LSTM(64, return_sequences) → Dropout(0.2) → LSTM(32) → Dropout(0.2) → Dense(16, relu) → Dense(1)`, 36,257 params, Adam + MSE, batch 256, EarlyStopping(patience 5), ReduceLROnPlateau. Trained 6 epochs × ~420 s on 1,023,000 sequences of shape (30, 26).

Five concrete reasons it lost — this is the analysis that impresses:

1. **The 30-day window cannot see `lag_365`** — my single most important feature (30.2 % gain). The LSTM structurally cannot access year-ago demand.
2. **The exogenous features were never given to it.** It got raw sales + one-hots + three calendar columns = 26 features, versus 50 engineered features including 22 event-decay columns. It's not a fair architectural comparison; it's a fair *pipeline* comparison, and the pipeline is what ships.
3. **MinMaxScaler compresses the spikes.** Scaling to [0,1] against a Q4 maximum squashes ordinary days into a narrow band, and MSE on squashed values gives the model little gradient signal on 90 % of the data.
4. **It stopped improving after epoch 1** — `val_loss` 5.5066e-04 → 6.7264e-04 by epoch 6. It was overfitting or under-capacity from the start; more epochs would not have helped.
5. **Trees suit tabular data.** Piecewise-constant splits fit threshold effects ("if `days_to_christmas < 7`") in one node; an MLP/LSTM must approximate a step with smooth activations. Trees are also invariant to feature scale and robust to uninformative columns.

**One-line version for interviews:** *"I gave deep learning 33× more data and 42 minutes, and it was 2.9× worse — because the signal lives in engineered exogenous features and a 365-day lag, not in a 30-day sequence."*

## 5.7 The train/select loss mismatch (a strong point to volunteer)

All models train on **squared error**; MODEL1 is selected on **WMAPE** (`:1050`). Those optimise different things — MSE is dominated by the largest-volume rows squared, WMAPE by absolute error weighted by volume. The consequence shows up in the results: near-zero overall bias (+0.23) but −12.02 bias in the Black Friday window. MSE is symmetric, so the model splits the difference on rare high peaks.

**The fix, in order:** (1) sample-weight event rows (as MODEL3 does); (2) train on MAE/pseudo-Huber to match WMAPE; (3) quantile regression at τ=0.7–0.8 so the model deliberately over-forecasts where stockout cost > holding cost. That last one is the business-correct answer.

**Takeaways** — GBDT = additive residual fitting; XGBoost's regularised second-order objective suits mid-size tabular data; LightGBM's leaf-wise growth needs scale; CatBoost's ordered boosting suits small data; RF is variance reduction and this is a bias problem; the LSTM lost on pipeline, not just architecture; and my training loss doesn't match my selection metric.

**Q: "Explain gradient boosting."** — "It's an additive model fit greedily. Start with the mean. At each step compute the gradient of the loss with respect to the current prediction — for squared loss that's just the residual — fit a shallow tree to those gradients, and add it scaled by the learning rate. XGBoost extends this with a second-order expansion, so the split gain uses both gradients and Hessians, plus an explicit penalty of gamma per leaf and lambda on leaf weights. In my config that's 500 trees at learning rate 0.05, depth 6, lambda 1.0 — small conservative corrections rather than a few aggressive ones."

**Q: "Why not deep learning?"** — see §5.6; lead with the measured 45.81 % vs 16.06 %.

---

# Chapter 6 — Libraries

| Library | Where | Internal idea | Why here | Alternatives | Limitation in my use |
|---|---|---|---|---|---|
| **pandas** | everywhere | Columnar DataFrames over NumPy blocks; vectorised ufuncs | `groupby.shift/rolling` gives lag features in 4 lines (`:454-477`) | Polars (lazy, multithreaded), DuckDB | Single-threaded; whole-file reads with no cache (`tables.py:11`) |
| **NumPy** | FE, decay maths | Contiguous typed arrays, SIMD ufuncs | Vectorised event decay over the whole frame per event (`:588-633`) | — | — |
| **scikit-learn** | RF, metrics, demo M2, scaler | Uniform `fit/predict` estimator API | `HistGradientBoostingRegressor` gives boosting with zero extra deps (`seed:85`) | — | `HistGBR` lacks CatBoost's ordered boosting |
| **XGBoost** | M1 winner, M2 `peak_lift_pct` | Second-order boosting, level-wise, `tree_method="hist"` | Best WMAPE on 22k×50 | LightGBM, CatBoost | Pickle couples serving to library version |
| **LightGBM** | M3, M1 candidate, M2 `decay_lambda` | Leaf-wise growth, GOSS, EFB, histogram bins | Fast; won on the small city dataset | XGBoost | Over-parameterised at depth 10 on 2,160 rows |
| **CatBoost** | M2 notebook (5/7 targets) | Ordered boosting + ordered target statistics + oblivious trees | Best on 5,482 rows × 80 features | — | **Not in `requirements.txt`** — the root cause of the shipped-artifact mismatch |
| **joblib** | all serialization | Pickle + efficient NumPy array handling + optional mmap | One call to persist a fitted booster (`:1234`) | ONNX, `booster.save_model()` | Pickle = version coupling, no schema, arbitrary-code risk |
| **FastAPI** | API layer | Starlette ASGI + Pydantic validation + auto-OpenAPI | Typed contracts and `/docs` for free | Flask, Django REST | Only 4 of 11 endpoints declare `response_model` |
| **Pydantic v2** | `schemas.py` | Rust-core (`pydantic-core`) validation from type hints | Request validation and response coercion | dataclasses + marshmallow | `date` typed as `str` → 500 instead of 422 on bad input |
| **pydantic-settings** | `config.py` | Env/`.env` → typed settings object | One relocatable config surface | `os.environ` | Default `cors_origins="*"` |
| **uvicorn** | server | uvloop + httptools ASGI server | Standard FastAPI runtime; `def` handlers → threadpool | gunicorn+uvicorn workers, hypercorn | Single process by default; `_state` not shared |
| **TensorFlow/Keras** | LSTM benchmark only | Autodiff graph, cuDNN LSTM kernels | Fair test of the deep-learning hypothesis | PyTorch | **Not in `requirements.txt`** — benchmark isn't reproducible from the repo |
| **SHAP** | M2 notebook | Shapley values; `TreeExplainer` computes them exactly in poly time | Model-agnostic per-feature attribution | permutation importance | Notebook-only; never surfaced in the API |
| **matplotlib / seaborn** | plots | Figure/axes rendering | `model_results.png` 4-panel report | plotly | Some figures built and never saved (`conti_script.py:303`) |
| **React 19 + Vite + TS** | frontend | Virtual DOM diffing; Vite = esbuild dev + Rollup build | Fast HMR, type-checked build (`tsc -b && vite build`) | Next.js, SvelteKit | `strict` not enabled in tsconfig |
| **Recharts** | all charts | Declarative React components over D3 scales | Composed chart, pie, area with ~20 lines each | Chart.js, visx | Re-renders whole chart on data change |
| **TanStack Table** | risk register | Headless — logic only, you own the markup | Sorting on 9 columns, default `severity desc` | AG Grid | No virtualisation configured |
| **Tailwind** | styling | Utility classes + JIT purge | Custom `surface/accent/danger` token palette | CSS Modules | Long className strings |

**Q: "Why joblib over pickle?"** — "joblib special-cases large NumPy arrays and stores them efficiently instead of going through the generic pickle protocol, which matters for tree ensembles with big weight arrays, and it supports mmap on load. But it's still pickle underneath, so it carries the same two problems: the class definitions must be importable at load time — which is why `artifacts.py` catches `ModuleNotFoundError` explicitly and tells you to install CatBoost — and unpickling executes code, so you should never load an untrusted file. For production I'd use XGBoost's native `save_model` to JSON, or export to ONNX, so serving doesn't depend on the training library's version."

**Q: "Why FastAPI over Flask?"** — "Three concrete reasons in this codebase. Pydantic validation means `ForecastRequest` rejects malformed bodies before my code runs, with a 422 and a field-level error. The OpenAPI schema is generated from the same types, so `/docs` is a live contract the frontend can read. And the `lifespan` context manager gives me a guaranteed load-before-serve hook for the three model artifacts. I did keep my handlers as `def` rather than `async def` — deliberately, because pandas work is blocking and FastAPI runs sync handlers in a threadpool instead of stalling the event loop."

---

# Chapter 7 — Feature Engineering

## 7.1 MODEL1 — 50 features, top-15 by gain

| Rank | Feature | Gain | Group | How computed | Weakness / failure case |
|---|---|---|---|---|---|
| 1 | `lag_365` | 0.3024 | A | `grp.shift(365)` | Needs a year of history → **cold-start SKUs impossible**; breaks on leap years and shifting-date holidays |
| 2 | `rolling_7` | 0.1589 | A | `grp.shift(1).rolling(7, min_periods=3).mean()` | Lags real turning points by ~3–4 days |
| 3 | `holiday_pipeline` | 0.0659 | D | `(thanksgiving_pre + christmas_pre + blackfriday_pre).clip(0,3)/3` | Loses which event drives it |
| 4 | `bfcm_overlap` | 0.0496 | D | `blackfriday_pre × cybermonday_pre` | Non-zero only ~4 days/yr → 12 examples in 3 years |
| 5 | `cybermonday_post_decay` | 0.0457 | C | `exp(−days_after / (post_win/2))` | — |
| 6 | `month` | 0.0423 | B | `date.dt.month` | Treated as ordinal: December(12) and January(1) are maximally distant |
| 7–11 | `*_pre/post_decay` (cyber, christmas, blackfriday, wedding) | 0.031→0.024 | C | see below | Windows hand-set, never validated |
| 12 | `lag_7` | 0.0233 | A | `grp.shift(7)` | Same weekday last week |
| 13 | `day_of_week` | 0.0199 | B | `dt.dayofweek` | Ordinal, same wrap-around issue |
| … | `valentines_pre_decay`, `valentines_post_decay` | **0.0000** | C | — | **Never split on. Two dead features.** |

**Event decay maths** (`model1_script.py:520-540`):
```
pre_decay  = exp(−days_before / (pre_window/4))   for days_before ≥ 0   → 1.0 on event day
post_decay = exp(−days_after  / (post_window/2))  for days_after  ≥ 1   → decays after
overlapping occurrences combined with np.maximum, never summed          (:621)
```
Why exponential: anticipation builds non-linearly — buying accelerates as the date nears. Why `pre_win/4`: a steeper τ makes the event-day peak unambiguously the maximum. Why `max` not `sum`: two occurrences of the same event should not double the effect.

**Group rationale**

| Group | Why it exists | Improvement |
|---|---|---|
| A Lag/rolling | Demand is autocorrelated yearly (seasonality) and weekly (habit) | Add `lag_364` (aligns weekday), EWMA instead of flat rolling, per-SKU normalised lags |
| B Time | Cheap calendar signal | **Cyclical encoding**: `sin(2π·m/12)`, `cos(2π·m/12)` — fixes the Dec/Jan discontinuity for `month`, `day_of_week`, `week_of_year` |
| C Decay | Encodes *proximity* to an event, which a date column cannot | Learn `pre_win`/`post_win` per event-brand instead of hardcoding; add promo-depth |
| D Interaction | Compressed events beat individual ones (rank 3 and 4) | Add `christmas × is_gift_buyer`; try more products systematically |
| E Segment | Channel and LTV shift conversion | ⚠ `segment_id` is assigned **randomly per row** (`:320`) — so these features are noise by construction |
| F Registry | Wedding/holiday registry is a leading indicator | Real registry data would be genuinely predictive; here it's synthetic |
| G Identity | Lets one model serve 30 SKUs | Target encoding or per-SKU embeddings instead of arbitrary label integers |

⚠ **Two label-encoding smells:** `brand_enc ∈ {0,1,2}` and `category_enc ∈ {0..10}` impose a false ordering. Trees cope by splitting repeatedly but waste depth. One-hot (3 and 11 columns) or target encoding would be cleaner. And `category_map` is built from `df["category"].unique()` (`:719`) — **row-order dependent**, so re-running on reordered data silently changes the encoding.

## 7.2 MODEL2 — 11 engineered features, ranked by SHAP

| SHAP | Feature | Formula | Reading |
|---|---|---|---|
| 22.67 | `avg_past_lift` | static per influencer | Track record dominates everything |
| 10.30 | `inf_content_fit` | `avg_past_lift × content_relevance` | Interaction beats both parents |
| 4.70 | `collab_maturity` | `log1p(ws_product_collab_count) × audience_overlap_score` | Repeat collabs compound, with diminishing returns |
| 4.53 | `month` | calendar | Seasonality |
| 3.38 | `is_gifted` | flag | Gifted posts convert *worse* — trust penalty ×0.90 in the generator |
| 3.28 | `is_video_post` | flag | +10 % in the generator |
| 3.01 | `traffic_lift_t0` | immediate click lift | Early proxy for eventual lift |
| 2.45 | `reach_x_er` | `log_followers × norm_engagement_rate` | Size × quality — neither alone suffices |

`content_relevance = 0.35·keyword + 0.25·hashtag + 0.40·embedding_similarity`. **Weakness:** SHAP is measuring my own generator's coefficients — `avg_past_lift` is literally a multiplier in the `peak_raw` formula. High SHAP here proves the model recovered the rule, not that the feature is causal in reality.

`ws_recency_score = exp(−days_since_last_ws / 60)`, with the sentinel 999 mapped to 0 (`cell 1`) — correct handling of "never posted" as a distinct state rather than a large number.

## 7.3 MODEL3 — 11 features

| Importance | Feature | Note |
|---|---|---|
| 4402 | `rolling_units_30d` | ⚠ **pinned to the constant 15.0 at serve time** (`demand_agent.py:103`) |
| 3584 | `income_velocity_30d` | `(income_t − income_{t−30}) / income_{t−30}` — rate of change, not level |
| 2603 | `day_of_year` | |
| 2563 | `price_velocity_30d` | ⚠ constant 0.01 at serve time |
| 2466/2112/1803 | home price / income / affordability | `affordability = price / income` |
| 986 | `category_Standard` | ⚠ always 0 at serve time (always Luxury) |
| 47 / 11 | `city_City_B` / `city_City_C` | ⚠ **always 0 at serve time** → every request scores as City_A |

**The velocity insight is the good idea here:** demand responds to the *derivative* of income, not its level. A wealthy static city buys less incrementally than a fast-growing one. That is a defensible piece of domain modelling — say it.

**Takeaways** — lags dominate MODEL1; interaction terms outrank most raw events; two features have exactly zero importance; segment features are noise by construction; MODEL2's SHAP reflects the generator; MODEL3's top three features are all hardcoded constants in production.

**Q: "Which feature would you drop and which would you add?"** — "Drop the two Valentine's decay columns — importance exactly zero, the model never split on them, and Valentine's isn't a home-goods event. Also drop the segment group: `segment_id` is assigned uniformly at random per row in my generator, so `ltv_tier_enc`, `channel_enc` and the buyer flags are structurally noise, and their importances confirm it — all under 0.002. What I'd add first is cyclical encoding for month and day-of-week — sine and cosine pairs — because right now December and January are maximally far apart as integers when they're adjacent in reality. Then a `days_since_last_stockout` feature, because censored demand is the classic blind spot in retail forecasting: my target is units *sold*, not units *demanded*, so any period where I was out of stock teaches the model that demand was low."

---

# Chapter 8 — Model Analysis

## 8.1 Side-by-side

| | MODEL1 baseline | MODEL2 uplift (shipped) | MODEL3 city |
|---|---|---|---|
| Algorithm | XGBRegressor | 7 × HistGradientBoostingRegressor | LGBMRegressor |
| Notebook algorithm | same | CatBoost×5, XGB×1, LGBM×1 | same |
| Trees × depth | 500 × 6 | 120 × 5 each | 700 × 10 |
| Features | 50 | 19 (`demo_feat_0..17` + `ws_flag`) | 11 |
| Train rows | ~19,000 | 3,500 | 2,160 |
| Validation | holdout, time split | none in the demo script | chrono 80/20 |
| Test result | WMAPE 16.06, R² 0.8823 | not measured | RMSE 2.22, R² 0.757 |
| Artifact | 1.65 MB | 7 files | 2.0 MB |

## 8.2 Complexity

```
TRAIN  histogram GBDT ≈ O(n_trees × n_features × (n·log n for pre-sort, then n_bins))
       M1: 500 × 50 × 19k    → seconds on a laptop
       LSTM: 6 epochs × 1.02M sequences × (30×26) → ~42 minutes  ← 3 orders of magnitude

PREDICT  O(n_trees × depth) comparisons per row — independent of n_train
       M1:  500 × 6  = 3,000 comparisons     ≈ tens of µs
       M2:  7 models × 120 × 5 = 4,200       ≈ tens of µs
       M3:  700 × 10 = 7,000                 ≈ tens of µs
       → one /api/demand/forecast ≈ 9 predict calls, well under 1 ms of pure compute
       → DataFrame construction and Pydantic serialisation dominate, not inference

MEMORY  resident models ≈ 3.8 MB total, ×1 per uvicorn worker
        pandas frames are the real memory cost: demand_with_predictions.csv is
        re-parsed per request with no cache (tables.py:11-17)
```

## 8.3 Why each model, why not the alternatives

**MODEL1 — XGBoost.** Chosen empirically: 16.06 vs LightGBM 17.83 vs RF 18.91, on the same time split. *Why not LightGBM:* leaf-wise growth overfits at this data size. *Why not RF:* bias reduction is what sharp event peaks need. *Why not ARIMA/Prophet:* 44 exogenous regressors with conditional brand/category effects don't fit the univariate frame — though I should have run seasonal-naive as a floor, and didn't. *Why not the LSTM:* measured, 2.9× worse.

**MODEL2 — seven independent regressors.** *Why 7 separate models:* different targets have different best algorithms (CatBoost won 5, XGBoost and LightGBM one each), so per-target selection buys real accuracy. *Why not multi-output:* it would force one algorithm on all seven and can't exploit that. *Why it's still wrong:* the five lift horizons are an exponential curve — `lift_t = peak · exp(−λt/24)` — so predicting `peak` and `λ` and computing the rest in closed form would guarantee a monotone, physically-consistent curve. Right now nothing stops the five independent models from predicting a non-monotone curve. **This is the best "what would you change" answer you have.**

**MODEL3 — LightGBM.** Only one algorithm was tried — a gap. The sample weighting is the sophisticated part; the capacity (700 × depth 10 on 2,160 rows) is the mistake.

## 8.4 Production considerations

| Concern | Status |
|---|---|
| Model versioning / registry | **Not implemented** |
| Reproducibility | Seeds fixed (42) in all generators; no data or model hashes |
| A/B or shadow deploy | **Not implemented** |
| Drift detection | **Not implemented** |
| Retraining cadence | **Not implemented** — manual script runs |
| Prediction logging | **Not implemented** |
| Rollback | Replace the `.pkl` and restart |
| Latency SLO | **Not implemented** |
| Serving/training skew | **Known and severe** (`demand_agent.py:46-51`) |

**Q: "Your 7 lift models could produce a non-monotone decay curve. How do you fix it?"** — "Right now nothing prevents `lift_48h` from exceeding `lift_24h`, because the five horizon models are independent. Two fixes. The minimal one is to predict only `peak_lift_pct` and `decay_lambda` — which I already do — and compute the curve analytically as `peak × exp(−λ·t/24)`, which is exactly the generator's formula and is monotone by construction. That drops five models and guarantees consistency. The more general fix, if the real decay isn't exponential, is monotone constraints — XGBoost and LightGBM both support `monotone_constraints`, and I'd model the curve as cumulative decay so monotonicity is enforced in the split search itself."

---

# Chapter 9 — API + Frontend Contract

## 9.1 How the frontend talks to the backend

```
frontend/src/lib/api.ts
  const base = import.meta.env.VITE_API_URL ?? ''
  fetchJson<T>(path)          GET  → res.ok ? json : throw Error(text || statusText)
  postJson<T>(path, body)     POST + Content-Type: application/json

DEV   vite.config.ts proxies /api → http://127.0.0.1:8000
      ⚠ but `define` also sets VITE_API_URL = 'http://localhost:8000' when unset,
        so `base` is non-empty and requests go cross-origin, bypassing the proxy
        — which is why CORS must be permissive in dev.
PROD  frontend on Vercel (static) · backend deployment: Not implemented
```

## 9.2 Contract table

| Endpoint | Method | Request | Response | UI consumer |
|---|---|---|---|---|
| `/api/health` | GET | — | 8 flags + `messages[]` | gate + status pill |
| `/api/kpis/dashboard` | GET | — | 4 counters | KPI cards |
| `/api/meta/skus` | GET | — | `skus[]`, `count` | SKU dropdowns |
| `/api/demand/timeseries` | GET | `sku_id`, `from?`, `to?` | `points[]` | ComposedChart |
| `/api/signals/timeseries` | GET | `sku_id?`, `from?`, `to?` | `points[]` | BarChart (last 90 social) |
| `/api/inventory/summary` | GET | — | rows + by_warehouse | **unused by the UI** |
| `/api/risk/skus` | GET | — | `risks[]` | TanStack Table |
| `/api/brief/weekly` | GET | — | `BriefResponse` | brief card |
| `/api/influencer/summary` | GET | — | metrics + distribution | RMSE bar chart |
| `/api/simulate` | POST | sku, wh, extra, lead delta | 14 points + assumptions | drawdown chart |
| `/api/demand/forecast` | POST | `ForecastRequest` | `ForecastResponse` | agent page |

## 9.3 Patterns worth defending

- **Health gate then fan-out** (`App.tsx:191-203`) — one actionable error screen instead of five failed requests.
- **Criticality tiering** — only the influencer call has `.catch(() => null)`; the other four are required.
- **`Promise.all` for independent calls**, though the two SKU-scoped calls at `:227-233` are sequential and shouldn't be.
- **Error text propagates** — FastAPI's `HTTPException` detail reaches the UI banner verbatim.
- **Raw-JSON accordion** (`DemandForecastPage.tsx:555`) — proves numbers came from the API, not the UI. Demo this.

⚠ `types.ts` is hand-maintained and already drifted (`conti_model_loaded` missing); `DemandForecastPage` declares a *third* copy of the forecast types. Generate from OpenAPI instead.

**Q: "How do you handle backend errors in the UI?"** — "`fetchJson` checks `res.ok` and throws with the response body, so FastAPI's detail string surfaces directly. At the page level there are three tiers: if `/api/health` says the analytics files are missing, I render a setup component with the exact command to run plus the backend's own diagnostic messages — that's the common case and it's actionable. If a required data call fails, an inline red banner shows the message with a hint about port 8000. The influencer panel is explicitly optional so its failure is swallowed and the panel just shows a placeholder. The one inconsistency I'd fix is the simulator, which uses `alert()` instead of the inline pattern."

---

# Chapter 10 — Performance

**No profiling is implemented.** No timing middleware, no `cProfile`, no APM, no load test. The numbers below are analytical estimates from code structure and artifact sizes — say that plainly rather than inventing measurements.

## 10.1 Where time goes

| Path | Dominant cost | Estimate |
|---|---|---|
| `/api/demand/forecast` | 3 DataFrame constructions + 9 `predict()` + Pydantic serialise | sub-millisecond compute; ~1–3 ms total |
| `/api/risk/skus` | `read_csv` × 2 **+ O(N_inv × N_demand) Python loop** | dominated by CSV parse and the loop |
| `/api/kpis/dashboard` | same work again, from scratch | duplicate of the above |
| `/api/brief/weekly` | `compute_risks` a **third** time | triplicate |
| Dashboard page load | 6 endpoints, 3 of which each re-parse the demand CSV | worst offender |

## 10.2 Ranked bottlenecks and fixes

| # | Bottleneck | Evidence | Fix | Expected gain |
|---|---|---|---|---|
| 1 | CSV re-read per request, no cache | `tables.py:11-17` | Load once at startup into `_state`; invalidate on mtime | Removes parse cost from every request |
| 2 | `compute_risks` runs 3× per page load | `main.py:169, 262`; `brief.py:16` | One shared memoised call keyed on file mtime | ~3× less CPU on the read path |
| 3 | O(N_inv × N_demand) risk loop | `risk_engine.py:63-69` | `groupby("sku_id").tail(28).agg()` + merge | Linear instead of quadratic |
| 4 | 7 sequential `predict()` on 1-row frames | `demand_agent.py:161-171` | Predict `peak` + `λ` only, compute curve analytically (§8.3) | 9 calls → 3 |
| 5 | Whole signal history sent, 90 points used | `App.tsx:235` | Pass `from=` — endpoint already supports it | Large payload reduction |
| 6 | Two sequential awaits for independent calls | `App.tsx:227-233` | `Promise.all` | ~½ the latency on SKU change |
| 7 | 1-row DataFrame per predict | `demand_agent.py:64` | Reuse a preallocated NumPy array | Minor, but the largest remaining per-request cost |

## 10.3 Memory

Models ~3.8 MB resident per worker (`best_model.pkl` 1.65 MB, `conti_model.pkl` 2.0 MB, M2 bundle small). Trivial. The real pressure is transient pandas frames — every request materialises a full copy of `demand_with_predictions.csv`, and `compute_risks` calls `.copy()` on both inputs (`risk_engine.py:57-59`) before iterating.

## 10.4 What I'd measure first

Timing middleware logging `endpoint, duration_ms, rows_read`; then `cProfile` on `/api/risk/skus`; then `locust`/`k6` at 50 concurrent users to find the threadpool ceiling. Fix #1 and #2 before optimising anything else — they're one afternoon of work and remove most of the cost.

**Q: "Your dashboard is slow. Debug it."** — "First I'd confirm where the time is, not guess — timing middleware on each endpoint plus a row-count log. My prior is that it's I/O, not inference: the models are under four megabytes and a predict call is thousands of comparisons, but `tables.py` re-reads the demand CSV from disk on every single request with no cache, and three separate endpoints each trigger a full risk computation over that frame. So a single page load parses the same file three times and runs the same O(inventory × demand) loop three times. The fixes in order: cache the DataFrame at startup keyed on file mtime; collapse the three risk computations into one memoised call; vectorise the loop into a groupby-aggregate and a merge. If it were still slow after that, I'd move to columnar storage — Parquet or DuckDB — so I can push filters down instead of loading everything into memory."

---

# Chapter 11 — Interview Preparation

**Q1. Tell me about this project.** → 60-second version: problem (three demand forces), approach (three models, additive composition), stack (FastAPI + React, GBDT), result (WMAPE 16.06 %, beat an LSTM at 45.81 %), honest scope (synthetic data, hackathon).

**Q2. Why XGBoost?** → Empirical: 16.06 vs LGBM 17.83 vs RF 18.91 on the same time-based split, selected by lowest WMAPE. Theory: level-wise growth is more conservative than leaf-wise at 22k rows; second-order objective with explicit L1/L2 on leaf weights. *Follow-up: "would it still win at 10M rows?"* → "Probably not — LightGBM's histogram binning and GOSS are built for that scale; I'd re-run the comparison rather than assume."

**Q3. How did you split train/test and why?** → Time-based at 2024-10-01, test = Oct–Dec 2024. Random splits leak with lag/rolling features and would flatter the model. I chose the holiday quarter deliberately as the hardest window. *Mistake to avoid:* saying "80/20" — it's a date cut, and the ratio follows from it.

**Q4. Where could data leakage occur, and how did you prevent it?** → `sort_values(["sku_id","date"])` before lags (`:447`); `shift(1)` **before** `rolling()` (`:463`) so the current day is excluded; time-based split. Self-flag: I pass the test set as `eval_set` — harmless without early stopping, bad habit regardless.

**Q5. Walk me through a request.** → Chapter 1 §1.5.

**Q6. What's the single biggest weakness?** → Training/serving skew: `demand_agent.py:46-51` fills lags and event decays with constants, and those carry most of the model's importance. Fix = feature store + analytic event decay + recursive lags for future dates.

**Q7. Your R² is 0.88 — good?** → Meaningless in absolute terms: the target is a generator I wrote plus 8 % noise, and I never computed a seasonal-naive baseline. Good relative to the three alternatives tested.

**Q8. How would you deploy this?** → Containerise the API, gunicorn+uvicorn workers, models baked into the image with a version tag, `/api/health` as the readiness probe, frontend already static on Vercel. Then: prediction logging, a nightly retrain job, and drift monitoring on feature distributions. All currently **not implemented**.

**Q9. How do you know when to retrain?** → Not implemented today. I'd trigger on (a) rolling WMAPE over the last 4 weeks exceeding a threshold, (b) PSI/KL drift on key features, (c) calendar cadence before each peak season. My `metrics_by_week.csv` is exactly the artefact that monitoring would produce continuously.

**Q10. Explain WMAPE and why not MAPE/RMSE.** → `Σ|y−ŷ| / Σ|y| × 100`. MAPE divides per row so it explodes for low-volume SKUs and weights a 1-unit SKU like a 300-unit one. RMSE is in units, not comparable across SKUs, and over-penalises the rare large errors. WMAPE is scale-free *and* volume-weighted, which matches the business. Caveat I volunteer: I train on MSE and select on WMAPE — a mismatch (§5.7).

**Q11. What if demand is censored by stockouts?** → Real blind spot. My target is units *sold*, not units *demanded*, so any stockout period teaches the model demand was low, and it under-forecasts exactly the SKUs that ran out — a self-reinforcing error. Fixes: flag stockout days and exclude or reweight them, or treat them as right-censored and use a censored likelihood / Tobit-style approach.

**Q12. Design this for 1,000 stores × 100k SKUs.** → Storage: Parquet/warehouse, partitioned by date and store. Features: a feature store with point-in-time correctness so serving matches training. Training: one global model with store/SKU embeddings or target encoding, not 100M models; distributed with Spark or Ray. Serving: precompute the batch forecast nightly into a KV store; keep the online path for what-if only. Monitoring: per-segment WMAPE dashboards.

**Q13. What did you learn?** → That measurement beats intuition: I expected LightGBM to win and predicted so in a comment; XGBoost did. I expected the LSTM to be competitive on a million rows; it was 2.9× worse. And that the gap between offline metrics and a live endpoint is where most of the real engineering is.

**Common mistakes checklist:** claiming real data · calling the brief AI-generated · quoting notebook M2 metrics for the deployed model · saying "80/20 split" · calling `embedding_similarity` an embedding · presenting SHAP as feature selection · saying the dashboard calls the model · being unable to name a defect.

---

# Chapter 12 — Interview Attack Round

**A1. "Your model is 84 % accurate on data you generated yourself. Why should I care?"**
"You shouldn't care about the number — you should care about the method. The R² measures how well GBDT inverts a function I wrote, and I'd say so before you asked. What transfers is the pipeline: the anti-leakage lag construction, the time-based split on the hardest quarter, and an evaluation suite that slices error eight ways and caught a −12-unit bias in the Black Friday window. Point that at real data tomorrow and the harness is what tells you whether the model works. The number is a hackathon artefact; the harness isn't."

**A2. "You call it a three-model pipeline, but the weights are hardcoded to 1. That's not an ensemble, it's addition."**
"Correct, and the honest reason is units, not sophistication: Model 2's target is a percentage and Model 3's is a unit count, so the algebra was dictated by the targets rather than learned. A real ensemble needs a joined training table where all three signals coexist for the same rows, and that dataset doesn't exist — the three generators are independent. What I'd do with real data is fit the combination weights on a held-out set, or better, make it a two-stage model: baseline prediction as a feature in an uplift model. There's also a double-counting risk I should name — if an influencer campaign is *why* city demand rose, I'm adding the same units twice."

**A3. "Your live endpoint fills the most important features with the constant 20. What is it actually predicting?"**
"Very little of value, and that's the defect I'd fix first. `lag_365` and `rolling_7` are 46 % of the model's gain and both are constants at request time, so the live number carries the calendar and product-identity signal only. My measured WMAPE describes the batch path, where features are real, not the agent endpoint. The fix is a feature store — the ETL already computes those exact columns per SKU-date — plus computing event decays analytically from the request date using the same function training uses. Until then I'd treat the agent as a what-if UI, not a production forecaster, and I'd say that in a design review."

**A4. "You shipped a demo model and quote a notebook's metrics. Isn't that dishonest?"**
"It would be if I didn't flag it, which is why it's the third item in my own defect list. The cause is a dependency decision: the notebook's best models are CatBoost, CatBoost isn't in the backend requirements, so I wrote an sklearn-only stand-in so the API would load on any machine. The consequence is that `models/*_features.json` contains `demo_feat_0` through `17` rather than the 80 real features. Two fixes: add CatBoost to requirements, or export to ONNX so serving doesn't depend on the training library at all. The second is better — it fixes the version-coupling problem too."

**A5. "Why should I believe you understand boosting and didn't just call `.fit()`?"**
"Ask me to derive it. XGBoost's objective is a second-order Taylor expansion of the loss plus `γT + ½λ‖w‖²`. Setting the derivative to zero gives the optimal leaf weight `w* = −G/(H+λ)`, and substituting back gives the split gain as `½[G_L²/(H_L+λ) + G_R²/(H_R+λ) − G²/(H+λ)] − γ`. That's why `min_child_weight` is 5 in my config — it's a floor on the sum of Hessians in a leaf, and for squared loss the Hessian is 1, so it's effectively 5 rows minimum. And it's why `reg_lambda` shrinks predictions toward zero: it sits in the denominator of the leaf weight."

**A6. "Your risk engine is just three if-statements. Where's the ML?"**
"Deliberately nowhere, and I'd defend that. I have no labelled risk data — nobody tagged historical positions as 'should have reordered' — so a supervised classifier has nothing to learn from. And buyers need to know *why* something is flagged; my API returns a `reasons` array saying 'projected demand during lead time exceeds available supply' plus 'recent demand trend is rising.' A probability of 0.73 is not actionable in the same way. The ML is upstream, in the run-rate the rules consume. What I'd concede is that the thresholds — 1.15, ten weeks, 0.92 — are hand-tuned to make the demo look right, and with real data they should be fit to a cost function that trades stockout cost against holding cost."

**A7. "You claim the LSTM failed. Maybe you just built it badly."**
"Partly true, and I'd rather concede the specific version than the general one. It only got 26 features — raw sales, one-hots, three calendar columns — while the trees got 50 engineered features including 22 event-decay columns. The 30-day window structurally cannot see `lag_365`, which is my top feature. And MinMax scaling against a Q4 peak compresses ordinary days into a narrow band, which starves MSE of gradient signal. So it's not proof that no neural network can win — it's evidence that on this data, with equal engineering effort, the tree pipeline won by 2.9×. A fair rematch would give the LSTM the same exogenous features and a 400-day window, and honestly I'd expect a Temporal Fusion Transformer to be the credible contender, not a plain LSTM."

**A8. "Your predictions change after a server restart. Explain."**
"That's a genuine bug and it's mine. I use Python's `hash()` for two feature values — `category_enc = hash(product_id) % 10` and a filler `(hash(col) % 100)/100` for unmapped MODEL2 columns. String hashing is salted per process via PYTHONHASHSEED, so the same request returns different numbers after a restart. Non-determinism in a prediction service is unacceptable. The fix is a stable hash — `hashlib.md5` on the encoded string, or better, the actual category mapping the training pipeline used, which is what the model expects anyway."

**A9. "The city selector doesn't change the city prediction for most cities. Did you test this?"**
"No, and it's two bugs compounding. First, the UI offers 19 cities and `CITY_PROFILES` defines 7, so twelve fall through to a shared default and produce identical output. Second and worse, the city dummy columns never fire: the feature names are `city_City_B` and `city_City_C`, my code splits on underscore and takes the last token — 'B' and 'C' — then compares that to the request city, which is 'Mumbai'. So every request silently scores as City_A, the reference level. There are no tests in the Python codebase, which is how both survived. The first tests I'd write are exactly these: a parametrised check that distinct cities produce distinct predictions, and a unit test on the feature-synthesis functions asserting column names and values."

**A10. "If I gave you this codebase and one week, what would you do?"**
"Day 1: tests around `risk_engine` and the feature synthesizers — they're pure functions and both bugs above would have been caught. Day 2: fix the training/serving skew with a feature-store lookup and analytic event decays. Day 3: cache the CSV reads and vectorise the risk loop. Day 4: replace the five horizon models with the closed-form `peak × exp(−λt/24)` curve. Day 5: a seasonal-naive baseline and rolling-origin backtest so I can report skill instead of raw R². Day 6: prediction logging and a weekly WMAPE job — my `metrics_by_week` script is already the monitoring artefact. Day 7: containerise the backend, since only the frontend has a deployment path today."

---

# Chapter 13 — Revision Notes

## Architecture cheat sheet
```
React (Vite/TS/Tailwind/Recharts) ──HTTP──► FastAPI ──► services/
  App.tsx (dashboard tab)                      artifacts.py  → 3 models into _state
  DemandForecastPage.tsx (agent tab)           tables.py     → 6 CSV/JSON loaders
  lib/api.ts fetchJson/postJson                risk_engine.py→ threshold rules
                                               brief.py      → f-string summary
OFFLINE: model1_script → ws_model/*.pkl        demand_agent.py→ 3-model composition
         conti_script  → models/conti_model.pkl
         seed_..._demo → models/{7 targets}.pkl
         build_case_study_tables → analytics/*.csv + data/*.csv
```

## ML pipeline cheat sheet
```
generate → clean(sort, drop lag_365 NaN, impute) → engineer(50 feats, 7 groups)
→ encode(label maps, no scaling) → time-split 2024-10-01 → train RF/XGB/LGBM
→ select lowest WMAPE → XGBoost → joblib.dump(model + feature_cols)
→ ETL scores full history → CSV → dashboard reads CSV (no model on read path)
```

## Files / classes / functions to name
`config.Settings` · `schemas.ForecastRequest/ForecastResponse` · `artifacts.try_load_model1/2_bundle/conti` · `tables._read_csv` · `risk_engine.RiskRow/compute_risks/count_signal_spikes` · `brief.build_weekly_brief` · `demand_agent.run_forecast_agent` + 3 `_synthesize_*` · `main.lifespan/_state/_demand_frame`

## Formulas
```
GBDT        Fₘ = Fₘ₋₁ + ν·hₘ ;  squared-loss gradient = residual
XGBoost     w* = −G/(H+λ) ;  gain = ½[G_L²/(H_L+λ)+G_R²/(H_R+λ)−G²/(H+λ)] − γ
WMAPE       Σ|y−ŷ| / Σ|y| × 100
Event decay pre = exp(−d_before/(pre_win/4)) ; post = exp(−d_after/(post_win/2))
Interaction bfcm = bf_pre × cm_pre ; pipeline = (tg+xmas+bf).clip(0,3)/3
Lift curve  lift_t = peak_lift · exp(−λ·t/24)
Composition final = baseline + baseline·(peak_lift_pct/100) + city_units
Risk        expected = max(mean_act, mean_pred) × lead ; woc = stock/(rate×7)
            stockout ⟺ expected > stock×1.15 ; overstock ⟺ woc>10 AND trend<0.92
Velocity    income_velocity_30d = (iₜ − iₜ₋₃₀)/iₜ₋₃₀ ; affordability = price/income
```

## Numbers to have cold
```
M1  WMAPE 16.06 · R² 0.8823 · RMSE 32.81 · MAE 16.82 · bias +0.23 · P90 43.12 · n 2760
    RF 18.91 · XGB 16.06 · LGBM 17.83        50 features · 30 SKUs · 3 years
    best week 6.93 % · worst week 27.50 % (BF) · BF-window bias −12.02
    top feats lag_365 0.302 · rolling_7 0.159 · holiday_pipeline 0.066
M2  R² 0.9369 (6h) → 0.8117 (96h) · peak_lift_pct R² 0.9447 RMSE 11.62
    10,000 posts · 80 features · CatBoost 5/7 · SHAP top avg_past_lift 22.67
M3  RMSE 2.2173 · MAE 1.5853 · R² 0.7571 · 2,700 rows · 11 features
LSTM WMAPE 45.81 · RMSE 105.72 · 1,096,200 rows · 36,257 params · 6 epochs
```

## Red flags — never say these
1. "Real Williams-Sonoma data" → all synthetic, seeded
2. "The dashboard runs the model" → it reads pre-scored CSVs
3. "AI-generated brief" → f-strings (`brief.py`)
4. "My deployed influencer model has R² 0.94" → that's the notebook; the API loads a 19-feature demo
5. "I used embeddings" → `embedding_similarity` is a synthetic scalar
6. "I tuned with Optuna" → installed, never imported
7. "80/20 split" → time cut at 2024-10-01
8. "SHAP-based feature selection" → SHAP is post-hoc only
9. "It scales because it's stateless" → the CSV re-read is the bottleneck
10. "The simulator forecasts 14 days" → it replays the last 14 historical rows

## Defects to volunteer, in order
1. Training/serving skew — constants for lags and decays (`demand_agent.py:46-51`)
2. City dummies never fire → every request scores as City_A (`:112`)
3. Shipped M2 bundle ≠ notebook M2 bundle (CatBoost not in requirements)
4. Lift curve 5 values vs 6 axis labels (`:165` vs `Page:49`)
5. `hash()` → non-deterministic predictions across restarts (`:35, :84`)
6. No cache; `compute_risks` runs 3× per page load
7. `/api/simulate` replays history and labels it a forecast (`main.py:201-204`)
8. No Python tests, no naive baseline, no monitoring, no backend deployment

## Last-minute checklist
Know the three models and their metrics · know the composition formula · know the two anti-leakage lines (`:447`, `:463`) · know why XGBoost beat LightGBM and RF · know the LSTM numbers · know WMAPE vs MAPE · have three defects ready to volunteer unprompted · never quote a number without its caveat.

---
**End of the handbook.** Chapters 1–4 are separate files in `docs/handbook/`.
