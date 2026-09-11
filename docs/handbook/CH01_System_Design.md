# SurgeAI / Control Tower — ML Internship Interview Handbook

**Repository:** `SurgeAI` (git remote: `github.com/AyushShevde/SurgeAI.git`)
**Handbook version:** 1.0
**Scope rule:** every statement in this handbook is traceable to a file and line in this repository. Where a capability does not exist, it is written as **"Not implemented in the current codebase."**

---

## Chapter 1 — Complete System Design

> Read this chapter until you can redraw the diagrams from memory on a whiteboard. In an internship interview you will be asked "walk me through your project" within the first 4 minutes. That answer comes entirely from this chapter.

---

### 1.1 What this system actually is

SurgeAI is a **two-surface application over one shared set of offline-trained models**:

| Surface | Entry point | What it does | Are models called at request time? |
|---|---|---|---|
| **Control Tower dashboard** | `frontend/src/App.tsx` | KPIs, demand vs. prediction chart, social-signal chart, risk register, weekly brief, what-if stock drawdown | **No.** It reads pre-computed CSVs. Predictions were baked in offline by `scripts/build_case_study_tables.py:245`. |
| **Demand Forecast Agent** | `frontend/src/DemandForecastPage.tsx` | Composes three models into a single demand number with an influencer lift curve | **Yes.** `POST /api/demand/forecast` → `run_forecast_agent()` calls `.predict()` on three loaded models (`backend/app/services/demand_agent.py:138, 161, 184`). |

This split is the single most important architectural fact about the project, and the one candidates most often fumble. Learn to say it in one sentence:

> "The dashboard is served from pre-computed analytics tables — offline batch scoring. The forecast agent is a live inference path where three models are held in process memory and called synchronously per request."

---

### 1.2 High-level architecture (ASCII)

```
                        ┌──────────────────────────────────────────────┐
                        │            OFFLINE / TRAINING PLANE          │
                        │   (run manually from repo root, not served)  │
                        └──────────────────────────────────────────────┘

  scripts/model1_script.py          scripts/seed_and_train_        scripts/conti_script.py
  (also notebooks/MODEL1_XGBOOST)    influencer_demo.py             (also notebooks/conti.ipynb)
  notebooks/MODEL1_LSTM.ipynb        notebooks/MODEL2_ML.ipynb
          │                                  │                              │
          │ synth sales + features           │ synth influencer posts       │ synth city economics
          ▼                                  ▼                              ▼
  ws_demand_dataset/                  features_engineered.csv        luxury_surge_dataset.csv
    ml_ready_data.csv                        │                              │
          │                                  ▼                              ▼
          ▼                            models/{target}_best.pkl        models/conti_model.pkl
  ws_model/best_model.pkl              models/{target}_features.json   models/conti_features.json
  ws_model/feature_cols.pkl
          │
          └──────────────┬────────────────────────────────────────────────────┐
                         ▼                                                    │
        scripts/build_case_study_tables.py   ← ETL / batch scoring            │
                         │                                                    │
        ┌────────────────┼───────────────────────┐                            │
        ▼                ▼                       ▼                            │
  analytics/       analytics/              data/inventory.csv                 │
  demand_with_     influencer_metrics.json data/signals.csv                   │
  predictions.csv  influencer_sample.csv                                      │
        │                                                                     │
════════╪═════════════════════════════════════════════════════════════════════╪═════
        │                    ONLINE / SERVING PLANE                           │
        ▼                                                                     ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI  (backend/app/main.py)                           │
│                                                                                   │
│  lifespan startup (main.py:36-48)                                                 │
│    artifacts.try_load_model1()        → _state["model1"], _state["feature_cols"]   │
│    artifacts.try_load_model2_bundle() → _state["model2"] (dict of 7 regressors)    │
│    artifacts.try_load_conti_model()   → _state["conti"], _state["conti_feats"]     │
│                                                                                   │
│  ┌──────────────── PATH A: file-driven ──────────┐  ┌── PATH B: model-driven ───┐ │
│  │ tables.py  (pandas.read_csv, no cache)        │  │ demand_agent.py           │ │
│  │      │                                        │  │   _synthesize_m1_features │ │
│  │      ├─► risk_engine.compute_risks()          │  │   _synthesize_m2_features │ │
│  │      ├─► risk_engine.count_signal_spikes()    │  │   _synthesize_conti_feats │ │
│  │      └─► brief.build_weekly_brief()           │  │        │                  │ │
│  │                                               │  │        ▼                  │ │
│  │  /api/health   /api/meta/skus                 │  │  model1.predict()         │ │
│  │  /api/demand/timeseries  /api/signals/…       │  │  model2[t].predict() ×7    │ │
│  │  /api/inventory/summary  /api/risk/skus       │  │  conti.predict()          │ │
│  │  /api/brief/weekly  /api/kpis/dashboard       │  │        │                  │ │
│  │  /api/simulate  /api/influencer/summary       │  │        ▼                  │ │
│  └───────────────────────────────────────────────┘  │  POST /api/demand/forecast│ │
│                                                     └───────────────────────────┘ │
│  CORSMiddleware (main.py:52-58)  ·  Pydantic response models (schemas.py)          │
└───────────────────────────────────────────────────────────────────────────────────┘
                         │  JSON over HTTP
                         ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│                      React 19 + Vite + Tailwind  (frontend/src)                   │
│                                                                                   │
│   main.tsx ──► App.tsx ──┬── Dashboard tab  (Recharts + TanStack Table)            │
│                          └── DemandForecastPage.tsx  (Recharts pie / area)         │
│                                                                                   │
│   lib/api.ts : fetchJson()  postJson()   base = import.meta.env.VITE_API_URL       │
│   dev: vite.config.ts proxies /api → http://127.0.0.1:8000                         │
└───────────────────────────────────────────────────────────────────────────────────┘
                         │
                         ▼
                       Browser
```

---

### 1.3 Component responsibilities

| Component | File | Responsibility | Key evidence |
|---|---|---|---|
| **App bootstrap** | `backend/app/main.py:36-58` | Async `lifespan` loads 3 model artifacts into a module-level dict `_state`; mounts CORS | `_state` defined at `main.py:25-33` |
| **Config** | `backend/app/config.py` | Pydantic-settings `Settings` class; resolves every artifact path relative to `root()` | `root()` at `config.py:28-31`; `_default_project_root()` at `:6-7` |
| **Artifact loader** | `backend/app/services/artifacts.py` | Defensive `joblib.load` of MODEL1, the 7-target MODEL2 bundle, and CONTI; returns `(obj, feats, messages)` and never raises | `try_load_model1:21`, `try_load_model2_bundle:45`, `try_load_conti_model:72` |
| **Table loader** | `backend/app/services/tables.py` | Thin `pandas.read_csv` wrappers that return `None` instead of raising | `_read_csv:11-17` |
| **Risk engine** | `backend/app/services/risk_engine.py` | Rule-based stockout/overstock classification + WoW signal spike counter | `compute_risks:50`, `count_signal_spikes:127` |
| **Brief generator** | `backend/app/services/brief.py` | Template string assembly over risk output — **not an LLM** | `build_weekly_brief:11-53` |
| **Forecast agent** | `backend/app/services/demand_agent.py` | Synthesizes feature vectors, calls 3 models, composes final demand | `run_forecast_agent:121-209` |
| **Schemas** | `backend/app/schemas.py` | Request/response contracts (`ForecastRequest`, `ForecastResponse`, `SimulateRequest`, …) | whole file, 83 lines |
| **Dashboard UI** | `frontend/src/App.tsx` | 6 parallel fetches on mount, SKU selector, risk table, what-if form | `loadCore:187-217` |
| **Agent UI** | `frontend/src/DemandForecastPage.tsx` | Form → single POST → pie + area chart + insight chips | `runForecast:234-261` |
| **HTTP client** | `frontend/src/lib/api.ts` | `fetchJson` / `postJson`, throws on `!res.ok` | 24 lines total |

**Not implemented in the current codebase:** database, ORM, message queue, cache layer (Redis/memcached), authentication/authorization, rate limiting, Dockerfile, CI pipeline, unit or integration tests, model registry, feature store, request logging/tracing, retraining scheduler.

---

### 1.4 Request lifecycle — Path A (`GET /api/risk/skus`)

```
Browser                FastAPI               tables.py              risk_engine.py         Disk
   │                      │                      │                        │                 │
   │ GET /api/risk/skus   │                      │                        │                 │
   ├─────────────────────►│                      │                        │                 │
   │                      │ _demand_frame()      │                        │                 │
   │                      ├─────────────────────►│ load_demand_predictions│                 │
   │                      │                      ├────────────────────────┼── read_csv ────►│
   │                      │                      │◄───────────────────────┼── DataFrame ────┤
   │                      │                      │  (if None → load_sales_fallback)         │
   │                      │◄─────────────────────┤                        │                 │
   │                      │ load_inventory()     │                        │                 │
   │                      ├─────────────────────►├──────────── read_csv ──┼────────────────►│
   │                      │◄─────────────────────┤                        │                 │
   │                      │ compute_risks(demand, inventory)              │                 │
   │                      ├───────────────────────────────────────────────►│                │
   │                      │        for each inventory row:                 │                │
   │                      │          filter demand by sku_id               │                │
   │                      │          _mean_daily() over last 28 rows       │                │
   │                      │          _trend_ratio() 7d vs prior 7d         │                │
   │                      │          classify stockout / overstock / ok    │                │
   │                      │◄───────────────────────────────────────────────┤                │
   │◄─ {"risks":[…],"count":N} ─┤                                          │                │
```

**Critical detail for interviews:** there is **no caching**. `tables.py:11-17` re-reads the CSV from disk on *every* request, and `/api/kpis/dashboard` (`main.py:255-269`) recomputes the full risk sweep a second time. A dashboard page load triggers 6 endpoints (`App.tsx:191-203`), several of which each re-read `demand_with_predictions.csv`. This is the #1 optimization the interviewer will ask you to identify. (Detailed treatment in Chapter 10.)

---

### 1.5 Request lifecycle — Path B (`POST /api/demand/forecast`)

```
DemandForecastPage.runForecast()               (frontend/src/DemandForecastPage.tsx:234)
        │  body = {product_id, city, date, campaign_active, influencer{…}}
        ▼
postJson('/api/demand/forecast', body)          (frontend/src/lib/api.ts:13)
        │
        ▼
FastAPI validates against ForecastRequest        (backend/app/schemas.py:57-62)
        │
        ▼
demand_forecast()                                (backend/app/main.py:272-290)
        │   passes _state models as a plain dict
        ▼
run_forecast_agent()                             (backend/app/services/demand_agent.py:121)
        │
        ├── STEP 1  BASELINE  ─────────────────────────────────────────────┐
        │   _synthesize_m1_features(product_id, city, date, m1_feats)      │
        │     builds a 1-row DataFrame in the exact column order of        │
        │     feature_cols.pkl; fills lag_*/rolling_* with the constant    │
        │     20.0, event decays with 0.0, days_to_* with 365  (:46-52)    │
        │   baseline = model1.predict(X1)[0]                    (:139)     │
        │   fallback if model missing: baseline = 150.0         (:142)     │
        │                                                                  │
        ├── STEP 2  INFLUENCER UPLIFT (only if campaign_active AND         │
        │           influencer.id present)                      (:150)     │
        │   _synthesize_m2_features(influencer, m2_feat_names)             │
        │     feat[0] = log10(followers)/7 ; feat[1] = eng_rate*10 ;       │
        │     feat[2] = 1 if platform=="instagram" ;                       │
        │     every other column = (hash(col) % 100)/100        (:77-84)   │
        │   peak_lift_pct = bundle["peak_lift_pct"].predict(X2) (:161)     │
        │   decay_lambda  = bundle["decay_lambda"].predict(X2)  (:162)     │
        │   lift_curve = [lift_6h, lift_24h, lift_48h,                     │
        │                 lift_72h, lift_96h]                   (:165-171) │
        │                                                                  │
        ├── STEP 3  CITY GROWTH  ──────────────────────────────────────────┤
        │   _synthesize_conti_features(city, product_id, date, feats)      │
        │     income/house price from CITY_PROFILES dict        (:11-19)   │
        │     income_velocity_30d = 0.02 * wealth  (hard-coded) (:101)     │
        │     price_velocity_30d  = 0.01           (hard-coded) (:102)     │
        │     rolling_units_30d   = 15.0           (hard-coded) (:103)     │
        │   city_extra_units = conti.predict(Xc)[0]             (:185)     │
        │   fallback if model missing: 5.0                      (:188)     │
        │                                                                  │
        └── STEP 4  COMPOSITION  ──────────────────────────────────────────┘
            influencer_lift_units = baseline * (peak_lift_pct / 100)   (:192)
            final_demand = max(0, baseline + influencer_lift_units
                                          + city_extra_units)          (:193)
        │
        ▼
ForecastResponse{final_demand, breakdown, uplift, insights}   (schemas.py:78-83)
        │
        ▼
BreakdownPie + LiftCurveChart + InsightChips render          (DemandForecastPage.tsx:106,158,89)
```

#### The composition formula, stated plainly

```
final_demand = baseline_units
             + baseline_units × (peak_lift_pct / 100)
             + city_extra_units
```

It is an **additive ensemble of three heterogeneous models**, not a stacked or blended ensemble. Model 1 sets the level; Model 2 contributes a *multiplicative* percentage applied to Model 1's output; Model 3 contributes *additive* units. Be ready to defend why the influencer term is multiplicative and the city term is additive — the honest answer is that Model 2's target is a percentage (`peak_lift_pct`) while Model 3's target is a unit count (`extra_units_sold`, `scripts/conti_script.py:156`), so the units dictated the algebra.

---

### 1.6 Known correctness issues in the serving path (say these before the interviewer finds them)

| # | Issue | Evidence | Why it matters |
|---|---|---|---|
| 1 | **Inference features are synthesized, not real.** Lags, rolling means and event decays — which carry ~46% of MODEL1's importance (`ws_model/feature_importance.csv`: `lag_365` 0.302 + `rolling_7` 0.159) — are filled with the constants `20.0` and `0.0`. | `demand_agent.py:46-52` | The live forecast does not reflect the accuracy measured offline. This is the biggest single credibility gap in the project. |
| 2 | **Lift-curve length mismatch.** Backend returns **5** values; frontend labels **6** hours. | `demand_agent.py:22` `LIFT_HOURS=[6,12,24,48,72,96]`; curve built from 5 targets at `:165`; `DemandForecastPage.tsx:49` `HOURS` has 6 entries; `:159` maps by index | The chart shows `lift_24h` under the "12h" label and plots `0` for "96h". A real, demonstrable bug. |
| 3 | **Shipped MODEL2 artifacts are the demo bundle, not the notebook bundle.** `models/*_features.json` contain `demo_feat_0…demo_feat_17, ws_flag` (19 columns). The notebook trained on **80** real features. | `models/lift_24h_features.json`; `scripts/seed_and_train_influencer_demo.py:46`; notebook output `Features : 80` | The 0.94 R² you might quote for `peak_lift_pct` belongs to the *notebook* model, not to what the API loads. |
| 4 | **Artifact path drift.** `settings.root()` resolves to the **repo root**, so the API looks for `<root>/ws_model/best_model.pkl` and `<root>/models/conti_model.pkl`. The committed `.pkl` files live in `backend/ws_model/` and `backend/models/`; the root copies are git-ignored. | `config.py:6-7, 49, 64`; `.gitignore` lines `ws_model/*.pkl`, `models/*.pkl` | On a fresh clone the models silently fail to load and the agent falls back to `150.0` / `5.0` — the degraded state is *reported* honestly in `/api/health` but is easy to miss. |
| 5 | **`allow_origins="*"` with `allow_credentials=True`.** | `config.py:26` default; `main.py:52-57` | Browsers reject this combination; also an over-permissive default. |
| 6 | **`hash()` used for feature values.** `cat_enc = hash(product_id) % 10` and `(hash(col) % 100)/100`. | `demand_agent.py:35, 84` | Python's `str.__hash__` is randomized per process (PYTHONHASHSEED), so **the same request can return different predictions after a restart**. Non-determinism in a prediction service. |
| 7 | **`/api/simulate` "14-day forecast" is the last 14 *historical* rows.** | `main.py:201` `sku_d[...].tail(14)` | It replays past predictions as if they were the future. The response string calls it "daily variable forecasts from XGBoost model" (`main.py:204`). |

Presenting these yourself converts every one of them from a weakness into evidence of engineering judgement. Chapter 12 drills the exact wording.

---

### 1.7 Training pipeline (offline)

```
┌─ MODEL 1 — Baseline demand ───────────────────────────────────────────────────┐
│ scripts/model1_script.py  (1462 lines, 4 concatenated stages)                  │
│                                                                               │
│  Stage 1  :1-368     Synthetic data generator                                  │
│                      30 SKUs × 3 brands (WS/PB/WE) × 1096 days (2022-2024)     │
│                      units = base_demand × seasonality × event_effect          │
│                              × dow_mult × yoy_growth × noise      (:310-315)   │
│                      → sales_data.csv, product_hierarchy.csv, events_data.csv, │
│                        customer_segments.csv, registry_data.csv                │
│                                                                               │
│  Stage 2  :371-862   Feature engineering — 7 groups, 50 features               │
│                      A lag_7/30/365, rolling_7/30, trend_ratio_7_30  (:454)    │
│                      B month, dow, week, quarter, is_weekend, is_q4, dom       │
│                      C 11 events × (pre_decay, post_decay)           (:588)    │
│                      D bfcm_overlap, holiday_pipeline, spring_gifting (:645)   │
│                      E ltv_tier_enc, channel_enc, gift/registry flags (:673)   │
│                      F active_registries, items_fulfilled_this_month  (:696)   │
│                      G brand_enc, category_enc                        (:718)   │
│                      drops first year (lag_365 NaN)                   (:734)   │
│                      → ws_demand_dataset/ml_ready_data.csv                     │
│                                                                               │
│  Stage 3  :864-1262  Train 3 models, time-split at 2024-10-01         (:922)   │
│                      RandomForest / XGBoost / LightGBM                         │
│                      select by lowest WMAPE                           (:1050)  │
│                      → ws_model/best_model.pkl + feature_cols.pkl              │
│                                                                               │
│  Stage 4  :1264-1462 Evaluation suite → ws_model/test_results/*                │
│                      overall, by brand, by category, by SKU, by week,          │
│                      residuals, event-window accuracy, decile calibration      │
└───────────────────────────────────────────────────────────────────────────────┘

┌─ MODEL 2 — Influencer uplift ─────────────────────────────────────────────────┐
│ REAL PATH: notebooks/MODEL2_ML.ipynb  (4 executable cells)                     │
│   cell 0  generate 10,000 posts · 58 influencers · 12 products · 5 tiers       │
│   cell 1  feature engineering → 95 cols, 11 engineered, StandardScaler saved   │
│   cell 3  per target: CatBoost vs LightGBM vs XGBoost, TimeSeriesSplit(3),     │
│           pick lowest OOF RMSE, refit on 100%, save {target}_best.pkl          │
│           + SHAP importance for peak_lift_pct                                  │
│                                                                               │
│ DEMO PATH (what is actually committed): scripts/seed_and_train_influencer_     │
│   demo.py — 3500 rows × 18 gaussian "demo_feat_i" + ws_flag,                   │
│   HistGradientBoostingRegressor per target, sklearn-only so the API loads      │
│   without CatBoost installed                                        (:85-91)   │
└───────────────────────────────────────────────────────────────────────────────┘

┌─ MODEL 3 — City growth ("conti") ─────────────────────────────────────────────┐
│ scripts/conti_script.py  ≡ notebooks/conti.ipynb                               │
│   :1-168    generate 3 cities × 2 categories × 450 days = 2700 rows            │
│             target extra_units_sold from a piecewise non-linear velocity rule  │
│   :232      pd.get_dummies(city, category, drop_first=True)                    │
│   :243-249  chronological 80/20 split                                          │
│   :254-272  LGBMRegressor(700 trees, lr 0.025, depth 10)                       │
│             sample_weight = 1 + 2·(income_velocity_30d > 0.1)      (:267)      │
│   :280      predictions clipped to [0, 50]                                     │
│   :375-377  → models/conti_model.pkl + conti_features.json                     │
└───────────────────────────────────────────────────────────────────────────────┘

┌─ ETL / batch scoring ─────────────────────────────────────────────────────────┐
│ scripts/build_case_study_tables.py                                             │
│   :51-65   score ml_ready_data with best_model.pkl → predicted_units           │
│            (falls back to a 7-day rolling mean if pickles are absent)          │
│   :74-126  synthesize data/inventory.csv, forcing 2 stockout + 2 overstock     │
│            scenarios so the demo always shows risk                             │
│   :129-165 synthesize data/signals.csv (social + search volume per SKU-day)    │
│   :168-228 score features_engineered.csv → analytics/influencer_metrics.json   │
│            and influencer_sample.csv                                           │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Every dataset in this project is synthetic.** There is no real Williams-Sonoma, social-media or census data anywhere in the repository. Say this proactively; it is not a flaw (it is a hackathon constraint) but concealing it is fatal.

---

### 1.8 Inference pipeline (two distinct modes)

| | **Batch / offline scoring** | **Online / synchronous scoring** |
|---|---|---|
| Trigger | Manual: `python scripts/build_case_study_tables.py` | `POST /api/demand/forecast` |
| Model used | MODEL1 only (`best_model.pkl`) | MODEL1 + MODEL2 bundle (7 regressors) + CONTI |
| Feature source | Real engineered columns from `ml_ready_data.csv` | Synthesized constants + a few request fields |
| Output | `analytics/demand_with_predictions.csv` | JSON `ForecastResponse` |
| Latency budget | minutes (offline) | per-request; 9 `.predict()` calls on 1-row frames |
| Consumers | All Path-A dashboard endpoints | Forecast Agent page only |
| Evidence | `build_case_study_tables.py:245` | `demand_agent.py:139, 161-171, 185` |

---

### 1.9 Folder structure

```
SurgeAI/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py            Settings (pydantic-settings), all artifact paths
│   │   ├── main.py              FastAPI app + 10 endpoints + lifespan loader
│   │   ├── schemas.py           Pydantic request/response contracts
│   │   └── services/
│   │       ├── artifacts.py     joblib loaders (MODEL1 / MODEL2 bundle / CONTI)
│   │       ├── brief.py         weekly buyer brief (template strings)
│   │       ├── demand_agent.py  3-model composition + feature synthesis
│   │       ├── risk_engine.py   stockout/overstock rules + spike counter
│   │       └── tables.py        pandas CSV loaders
│   ├── models/                  DUPLICATE artifacts: conti_model.pkl (+ .json)
│   ├── ws_model/                DUPLICATE artifacts: best_model.pkl, feature_cols.pkl,
│   │                            feature_importance.csv, model_comparison.csv,
│   │                            model_results.png, test_results/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx                 dashboard shell + tab router (no react-router)
│   │   ├── DemandForecastPage.tsx  agent page
│   │   ├── lib/api.ts              fetchJson / postJson
│   │   ├── types.ts                Health, Kpis, Risk, Brief, SkuMeta
│   │   ├── main.tsx                React root
│   │   ├── App.css / index.css
│   │   └── assets/
│   ├── vite.config.ts              dev proxy /api → 127.0.0.1:8000
│   ├── tailwind.config.js          custom surface/accent/danger palette
│   ├── package.json                React 19, recharts 3, @tanstack/react-table 8
│   └── vercel.json                 SPA rewrite
├── scripts/
│   ├── model1_script.py                 gen + FE + train + eval (MODEL1)
│   ├── conti_script.py                  gen + train (MODEL3)
│   ├── seed_and_train_influencer_demo.py demo MODEL2 bundle (sklearn only)
│   ├── seed_demo_ml_ready.py            minimal ml_ready_data fallback
│   └── build_case_study_tables.py       ETL / batch scoring
├── notebooks/
│   ├── MODEL1_XGBOOST.ipynb   source of model1_script.py
│   ├── MODEL1_LSTM.ipynb      1.1M-row dataset + Keras LSTM benchmark
│   ├── MODEL2_ML.ipynb        real influencer pipeline (CatBoost/LGBM/XGB + SHAP)
│   └── conti.ipynb            source of conti_script.py
├── models/            *_features.json only (.pkl git-ignored)
├── ws_model/          metrics + plot + test_results (.pkl git-ignored)
├── data/              luxury_surge_dataset.csv (2700 rows); inventory/signals git-ignored
├── docs/              hackathon submission deck (.pptx)
├── README.md
├── vercel.json
└── .gitignore
```

Git-ignored, therefore **absent from a fresh clone** and regenerated by the scripts: `ws_demand_dataset/`, `models/*.pkl`, `ws_model/*.pkl`, `scaler.pkl`, `features_engineered.csv`, `training_dataset_full.csv`, `analytics/`, `data/inventory.csv`, `data/signals.csv`.

---

### 1.10 Dependency graph (Python imports)

```
                          app/main.py
                               │
        ┌──────────┬───────────┼────────────┬──────────────┬──────────────┐
        ▼          ▼           ▼            ▼              ▼              ▼
   app.config  app.schemas  services.   services.      services.     services.
        ▲                   artifacts     tables         brief      demand_agent
        │                       │           │              │              │
        │                       │           │              ▼              │
        │                       │           │      services.risk_engine   │
        └───────────────────────┴───────────┘              ▲              │
                (config is imported by artifacts & tables)  │              │
                                                            └─ main.py ────┘
                                                               also imports
                                                               risk_engine directly

 External:  fastapi · pydantic · pydantic-settings · pandas · numpy · joblib
            (+ scikit-learn / xgboost / lightgbm required implicitly at unpickle time)
```

Two properties worth naming in an interview:

1. **The graph is acyclic and one-directional.** `services/*` never imports `main`. Only `demand_agent` and `main` know about model objects; `tables`/`risk_engine`/`brief` are pure-pandas and unit-testable in isolation. That is good layering.
2. **`demand_agent.py` does not import `config` or `artifacts`.** Models are *passed in* as a dict from `main.py:280-288`. This is manual dependency injection, and it is why `run_forecast_agent` can be tested with fake models. Call this out — it reads as deliberate design.

---

### 1.11 Call graph (who calls what)

```
GET  /api/health            → artifacts state + 4 × Path.is_file()          main.py:68
GET  /api/meta/skus         → _demand_frame → tables.load_demand_predictions main.py:92
GET  /api/demand/timeseries → _demand_frame → filter/sort → records          main.py:101
GET  /api/signals/timeseries→ tables.load_signals → filter                   main.py:126
GET  /api/inventory/summary → tables.load_inventory → groupby warehouse      main.py:148
GET  /api/risk/skus         → _demand_frame + load_inventory
                                   → risk_engine.compute_risks               main.py:163
GET  /api/brief/weekly      → brief.build_weekly_brief
                                   → compute_risks + count_signal_spikes     main.py:173
GET  /api/kpis/dashboard    → compute_risks (AGAIN) + count_signal_spikes    main.py:255
GET  /api/influencer/summary→ tables.load_influencer_metrics + _sample       main.py:234
POST /api/simulate          → _demand_frame + load_inventory → drawdown loop main.py:183
POST /api/demand/forecast   → demand_agent.run_forecast_agent                main.py:272
                                   ├─ _synthesize_m1_features → model1.predict
                                   ├─ _synthesize_m2_features → 7 × predict
                                   └─ _synthesize_conti_features → conti.predict
```

**Frontend → backend map**

| UI element | Call | File |
|---|---|---|
| Page mount | 1 × `/api/health`, then `Promise.all` of `/api/kpis/dashboard`, `/api/meta/skus`, `/api/risk/skus`, `/api/brief/weekly`, `/api/influencer/summary` | `App.tsx:191-203` |
| SKU dropdown change | `/api/demand/timeseries?sku_id=…` then `/api/signals/timeseries?sku_id=…` (sequential, last 90 social points) | `App.tsx:223-241` |
| "Run simulation" | `POST /api/simulate` | `App.tsx:258-274` |
| "Generate Forecast" | `POST /api/demand/forecast` | `DemandForecastPage.tsx:234-261` |

Note the **health-gate pattern** at `App.tsx:193-196`: if `demand_predictions_present` is false the app stops and renders `EmptyState` with setup instructions instead of firing failing requests. That is a genuinely good defensive-UX decision worth mentioning.

---

### 1.12 Why this architecture — the design rationale you should give

| Decision | Where | Defensible rationale | Honest trade-off |
|---|---|---|---|
| **Three specialist models instead of one** | `demand_agent.py:121-193` | The three signals live on different grains: SKU-day sales, per-post hourly lift, city-month economics. One model would need a joined table that does not exist, and each source has a different update cadence. Separate models can be retrained independently. | No joint optimisation; errors add rather than cancel; no single loss function to tune; double-counting risk if an influencer campaign *is* the reason city demand rose. |
| **Additive composition, not stacking** | `demand_agent.py:192-193` | Interpretable and auditable — a buyer can see exactly how many units came from baseline vs. campaign vs. city. Stacking needs a common training table. | Leaves accuracy on the table; the weights are 1.0 by fiat, never learned or validated. |
| **Batch-scored CSVs for the dashboard** | `build_case_study_tables.py:245` | Removes the model from the read path; sub-second charts; the UI degrades gracefully when artifacts are missing (`main.py:76`). | Predictions go stale; no way to re-score without re-running the script; no lineage between a CSV row and the model version that produced it. |
| **Models held in a module-level dict** | `main.py:25-48` | Loads once per process instead of per request — the standard pattern for pickled sklearn/XGBoost models under uvicorn. | Global mutable state; memory duplicated per worker (`best_model.pkl` ≈ 1.7 MB, `conti_model.pkl` ≈ 2.0 MB, so ~4 MB × workers — acceptable here); no hot reload. |
| **Loaders that return `None` instead of raising** | `artifacts.py:36-41`, `tables.py:11-17` | The app always boots; `/api/health` surfaces exactly what is missing; a hackathon judge never sees a crashed server. | Silent degradation — a wrong answer (`baseline = 150.0`) is returned with a `200 OK`. Production systems should fail loudly or serve a `503`. |
| **Flat CSV storage** | `config.py:33-67` | Zero infrastructure, trivially inspectable, git-diffable, works on any machine in the room. | No indexing, no concurrent writers, full-file reads, no schema enforcement. |
| **FastAPI + Pydantic** | `main.py`, `schemas.py` | Automatic validation, automatic OpenAPI docs at `/docs`, native async, response-model coercion. | Adds a validation cost per request that is negligible next to the CSV reads. |
| **Vite dev proxy instead of CORS in dev** | `vite.config.ts:8-10` | Same-origin in development, so cookies/CORS never bite locally. | Production still relies on `CORS_ORIGINS`, which defaults to `*`. |
| **Tab state instead of a router** | `App.tsx:162` | Two pages; `react-router` would be ~15 kB and extra config for nothing. | No deep-linking, no browser back-button support, no code-splitting per route. |

---

### 1.13 Scalability analysis

Current scale (from the artifacts, not guessed):

| Quantity | Value | Source |
|---|---|---|
| SKUs in MODEL1 dataset | 30 | `model1_script.py:35-73` |
| Sales rows generated | 30 × 1096 ≈ 32,880 | `model1_script.py:210-213` |
| Test rows evaluated | 2,760 | `ws_model/test_results/metrics_overall.json` |
| Inventory rows served | SKUs × 2 warehouses = 60 | `build_case_study_tables.py:85` |
| Signal rows served | SKUs × days × 2 signal types | `build_case_study_tables.py:143-161` |
| MODEL2 training rows | 10,000 (real notebook) / 3,500 (demo) | notebook output; `seed_and_train_influencer_demo.py:38` |
| MODEL3 training rows | 2,700 | `data/luxury_surge_dataset.csv` |
| LSTM benchmark rows | 1,096,200 | `MODEL1_LSTM.ipynb` cell 0 output |

**Where it breaks, in order:**

1. **CSV re-reads per request** (`tables.py:11-17`). At 30 SKUs the file is small; at 100k SKUs `demand_with_predictions.csv` becomes hundreds of MB and every request pays a full parse. *Fix:* cache the DataFrame at startup with an mtime check, or move to Parquet/DuckDB, or a real warehouse.
2. **`compute_risks` is a Python loop over inventory rows with a full-DataFrame boolean filter inside** (`risk_engine.py:63-69`). Cost ≈ O(N_inventory × N_demand). *Fix:* pre-aggregate with a single `groupby("sku_id").tail(28).agg(...)` and merge — turns it into two vectorised passes.
3. **Double risk computation per dashboard load** — `/api/risk/skus` and `/api/kpis/dashboard` both call `compute_risks` (`main.py:169` and `:262`). *Fix:* one endpoint returning both, or memoise on the demand-file mtime.
4. **Single-process model state** (`main.py:25`). Multiple uvicorn workers each hold their own copy and there is no shared invalidation. *Fix:* accept per-worker copies (they are small) but add a model-version header, or move to a dedicated inference service.
5. **No async I/O.** Every handler is `def`, not `async def`, so FastAPI runs them in a threadpool — which is actually the correct choice for blocking pandas work, and worth saying explicitly because interviewers probe it.
6. **Synchronous 7-model MODEL2 call.** `run_forecast_agent` calls `.predict()` seven times on a single-row frame (`demand_agent.py:161-171`). Per-call overhead dominates. *Fix:* a `MultiOutputRegressor` or a single model with 7 outputs, or batch the requests.

**What already scales well:** the model artifacts are tiny (≈ 3.8 MB total), inference is CPU-only with no GPU dependency, the API is stateless apart from the read-only model cache, and the frontend is a static bundle deployable to a CDN (`vercel.json`).

---

### 1.14 Key Takeaways

- SurgeAI has **two independent runtime paths**: a file-driven dashboard (offline batch scoring) and a model-driven forecast agent (online inference). Never describe it as one pipeline.
- The forecast agent composes three models **additively**: `baseline + baseline × peak_lift_pct/100 + city_units` (`demand_agent.py:192-193`).
- All three models are **gradient-boosted decision trees** — XGBoost (selected by WMAPE), a 7-target bundle (CatBoost/XGBoost/LightGBM in the notebook, HistGradientBoosting in the shipped demo), and LightGBM.
- Models load **once at startup** into a module-level dict via FastAPI's `lifespan` (`main.py:36-48`); loaders never raise, so the API always boots and reports gaps through `/api/health`.
- **Every dataset is synthetic**, generated by seeded scripts. State this up front.
- The serving path has **seven known defects** (§1.6). Volunteering them is a strength; being caught by them is not.
- No database, cache, auth, tests, Docker, or CI exist. **Not implemented in the current codebase.**

---

### 1.15 Revision Notes (60-second recall)

```
STACK        FastAPI · Pydantic v2 · pandas · joblib · XGBoost · LightGBM · CatBoost(nb)
             React 19 · Vite · TypeScript · Tailwind · Recharts · TanStack Table

ENDPOINTS    10 total →  health · meta/skus · demand/timeseries · signals/timeseries ·
             inventory/summary · risk/skus · brief/weekly · kpis/dashboard ·
             influencer/summary · simulate(POST) · demand/forecast(POST)

3 MODELS     M1 baseline   XGBoost      WMAPE 16.06 %  R² 0.882   50 features
             M2 uplift     7 targets    lift_6/24/48/72/96h, peak_lift_pct, decay_lambda
             M3 city       LightGBM     RMSE 2.22  MAE 1.59  R² 0.757   11 features

FORMULA      final = baseline + baseline·(peak_lift_pct/100) + city_units

SPLIT        M1: time split at 2024-10-01 (test = holiday season, the hard case)
             M2: TimeSeriesSplit(n_splits=3), OOF RMSE selection
             M3: chronological 80/20

LOAD ORDER   lifespan → try_load_model1 → try_load_model2_bundle → try_load_conti_model
             → _state dict → served to run_forecast_agent as a plain dict

WEAK POINTS  synthesized inference features · demo M2 bundle shipped · lift-curve
             off-by-one · no cache · O(N×M) risk loop · hash() non-determinism ·
             simulate replays history · CORS "*" + credentials
```

---

### 1.16 Common Interview Questions — Chapter 1

**Q1. "Walk me through your project architecture in two minutes."**

**Ideal answer:**
"SurgeAI is a supply-chain control tower with two surfaces over one model layer. The first surface is a dashboard — KPIs, a demand-vs-prediction chart, a risk register and a weekly brief. That surface is served entirely from pre-computed CSVs: an ETL script scores the whole history offline with the trained XGBoost model and writes `demand_with_predictions.csv`, so no model runs on the read path and charts render in milliseconds. The second surface is a forecast agent. It's a single POST endpoint that loads three models in process memory at startup through FastAPI's lifespan hook and composes them: XGBoost gives the baseline units, a seven-target influencer bundle gives a peak lift percentage and a decay curve, and a LightGBM city model gives additive units from income and housing velocity. Final demand is baseline, plus baseline times the lift percentage, plus the city units. The frontend is React with Vite; in dev it proxies `/api` to uvicorn, in prod it's a static bundle with a configurable API base URL."

**Q2. "Why three models instead of one?"**

**Ideal answer:**
"Because the three signals live on different grains and come from different sources. Baseline demand is SKU-by-day retail sales. Influencer lift is per-post and measured in hours — six, twenty-four, up to ninety-six hours after a post. City growth is monthly macroeconomic data at city level. There is no single table where all three co-exist, so a single model would require a join I don't have data for. Splitting them also means each can be retrained on its own cadence and each stays interpretable — the API returns a breakdown so a buyer sees exactly how many units came from each source. The honest cost is that I'm adding three independently-trained outputs without a joint loss, so the errors compound rather than cancel, and the combination weights are fixed at one rather than learned."

**Q3. "What happens between the browser click and the number on screen?"**

**Ideal answer:**
"The form builds a `ForecastRequest` — product id, city, date, campaign flag and influencer stats — and `postJson` sends it to `/api/demand/forecast`. FastAPI validates it against a Pydantic model. The handler pulls the three models out of a module-level state dict populated at startup and hands them to `run_forecast_agent`. That function builds a one-row DataFrame per model in the exact column order each model was trained on, calls predict, composes the three outputs, and returns a `ForecastResponse` with the final number, a three-way breakdown, the uplift curve and a list of insight strings. React renders the breakdown as a donut and the curve as an area chart."

**Q4. "Where does this system break if I give you a thousand times more SKUs?"**

**Ideal answer:**
"The read path first. Every request re-reads the whole CSV with `pandas.read_csv`; there's no cache. At thirty SKUs that's free, at thirty thousand it dominates latency. I'd cache the frame at startup keyed on file mtime, then move to Parquet or DuckDB so I can push filters down instead of loading everything. Second, the risk engine loops over inventory rows in Python and filters the full demand frame inside the loop — that's O(inventory × demand). I'd replace it with a single groupby-tail-aggregate and a merge, which makes it two vectorised passes. Third, the dashboard computes risk twice per page load because two endpoints both call `compute_risks`; I'd merge them or memoise. After that the model layer itself is fine — the artifacts total under four megabytes and inference is CPU-only."

**Q5. "You said models load at startup. What if a model file is missing?"**

**Ideal answer:**
"The loaders in `artifacts.py` catch `ModuleNotFoundError` and generic exceptions and return `None` plus a message rather than raising, so the app always boots. `/api/health` reports which models loaded and surfaces the messages. The forecast agent then falls back to constants — 150 units baseline, 5 units city — and prepends a warning to the insights list. I'd argue that's the right call for a demo where a crashed server means a dead presentation, but it's wrong for production: it returns a fabricated number with a 200 OK. In production I'd return 503 for the forecast endpoint when a required model is absent, and keep the graceful degradation only for the non-critical panels."

**Q6. "What is the weakest part of this design?"**

**Ideal answer:**
"The inference feature vector. My baseline model's two most important features are `lag_365` and `rolling_7` — together about forty-six percent of total importance. At request time I don't have a history for an arbitrary product-city-date, so `_synthesize_m1_features` fills every lag and rolling column with the constant twenty and every event decay with zero. That means the live forecast doesn't inherit the sixteen-percent WMAPE I measured offline; offline accuracy was measured on real engineered features. The fix is a feature store: persist the lag and rolling columns per SKU-date at ETL time and look them up at request time, which is exactly what the batch path already does. I'd also need a rule for future dates, where lags have to be recursively forecast."

**Common mistakes to avoid on Chapter 1 questions**

| Mistake | Why it costs you |
|---|---|
| Saying "the dashboard calls the ML model" | It does not. Dashboard reads CSVs written offline. An interviewer who reads `main.py` will catch it. |
| Calling the composition an "ensemble" without qualification | It is a fixed additive combination, not bagging/boosting/stacking. Use the precise term. |
| Claiming real Williams-Sonoma or social data | Everything is generated by seeded scripts. Instant credibility loss. |
| Quoting the notebook's 0.94 R² for the deployed influencer model | The committed bundle is the 19-column demo model, not the 80-feature notebook model. |
| Saying "it scales because it's stateless" | True but incomplete — the CSV re-read is the actual bottleneck. Name it. |
| Describing the `/api/simulate` output as a forecast | It replays the last 14 historical predicted values (`main.py:201`). |

---

### 1.17 Pending — resume claim audit

You asked for a line-by-line audit of your resume bullets against the code, with file references wherever a claim is missing or overstated. **Paste your SurgeAI resume bullets and I will add them as a dedicated section**, formatted as:

| Resume claim | Status | Evidence / where it breaks |
|---|---|---|
| *(your bullet)* | Supported / Partially supported / **Not in code** | exact `file:line` |

From what is already visible, the README makes at least four claims that the code does not support, and these are pre-loaded for that audit:

| README claim | Location | Reality |
|---|---|---|
| "Generative AI Orchestration… narrative insights" listed as roadmap, but the UI labels the brief as generated intelligence | `README.md` roadmap; `brief.py:26-44` | The brief is Python f-string templating. No LLM anywhere. Correctly listed as roadmap — do not upgrade it to a delivered feature. |
| "real-time influencer signals" | `README.md` intro | `data/signals.csv` is synthesised by `build_case_study_tables.py:129-165` with `numpy` noise. No live ingestion. |
| "city-level economic growth indicators" | `README.md` intro | `luxury_surge_dataset.csv` is generated by `conti_script.py:29-60`. No external economic data source. |
| "decay-aware lift curve … over 96 hours" | `README.md` feature showcase | True in structure (`demand_agent.py:165-171`) but the frontend mislabels the axis and drops the 96h point (§1.6 issue #2). |

---

**End of Chapter 1.** Type **Continue** for Chapter 2 — Project Overview (problem statement, business motivation, why ML is appropriate, users, inputs, outputs, constraints, success criteria).
