# SurgeAI / Control Tower — ML Internship Interview Handbook

## Chapter 2 — Project Overview

> Chapter 1 answered *how the system is built*. This chapter answers *why it exists* and *what it is accountable for*. Interviewers open with "what problem does this solve?" — and the failure mode is a vague answer about "supply chain optimisation." You need a problem statement that is specific, a justification for ML that survives one follow-up question, and a definition of success that maps to numbers your code actually computes.

---

### 2.1 Problem statement

The problem the codebase actually attacks, stated in one paragraph:

> For a multi-brand home-goods retailer, daily SKU-level demand is driven by three forces that ordinary forecasting misses: **calendar events with asymmetric pre- and post-windows** (a 35-day build-up to Christmas and a 10-day hangover after it), **short-lived social/influencer spikes** that decay over hours rather than days, and **slow city-level economic shifts** that change how much of a category a market can absorb. A forecast that models only trend and seasonality will under-forecast the run-up to Black Friday, miss campaign spikes entirely, and treat every city as identical — producing stockouts on the SKUs that matter most and dead inventory on the ones that don't.

Broken into the three sub-problems the three models each own:

| # | Sub-problem | Modelled as | Target variable | Grain | Evidence |
|---|---|---|---|---|---|
| 1 | What is the **baseline** daily demand for this SKU? | Supervised regression on 50 engineered features | `units_sold` | SKU × day | `scripts/model1_script.py:794` `TARGET_COLUMN = "units_sold"` |
| 2 | If an influencer posts, **how big is the spike and how fast does it decay?** | 7 independent regressions (one per horizon/shape parameter) | `lift_6h, lift_24h, lift_48h, lift_72h, lift_96h, peak_lift_pct, decay_lambda` | post | `backend/app/services/artifacts.py:10-18` |
| 3 | Is this **city's economy** pushing extra units through this category? | Supervised regression on macro velocity features | `extra_units_sold` | city × category × day | `scripts/conti_script.py:156` |

And the two decision-support problems layered on top, which are **rule-based, not ML**:

| # | Sub-problem | Modelled as | Evidence |
|---|---|---|---|
| 4 | Which SKU × warehouse positions are at risk *right now*? | Deterministic threshold rules over demand run-rate, lead time and stock | `backend/app/services/risk_engine.py:84-93` |
| 5 | What happens to stock if I add a PO or lose a week of lead time? | Deterministic drawdown loop | `backend/app/main.py:219-223` |

**Say the boundary out loud in an interview:** items 1–3 are machine learning; items 4–5 are business logic. Candidates who blur this get punished when asked "so what did the model actually decide?"

---

### 2.2 Business motivation

Inventory error is asymmetric, and that asymmetry is what makes this worth solving:

```
                    UNDER-FORECAST                     OVER-FORECAST
                    ──────────────                     ─────────────
   immediate cost   lost sale                          working capital tied up
   second-order     customer buys from competitor      markdown to clear
   third-order      lost lifetime value                margin erosion + storage
   worst case       stockout during peak week          dead stock after peak week
                    (highest-margin days of the year)  (must be discounted hardest)
```

The code encodes exactly this asymmetry in two places, and both are quotable:

**1. The risk engine is deliberately conservative about stockouts.**

```python
# backend/app/services/risk_engine.py:73-78
mean_act, mean_pred = _mean_daily(sku_d)
trend = _trend_ratio(sku_d)
# Use max of actual and predicted run-rate for conservative stockout view
run_rate = max(mean_act, mean_pred)
expected  = run_rate * lead
woc       = stock / max(run_rate * 7, 0.01)
```

Taking `max(actual, predicted)` biases toward flagging stockouts. It says: *when the model and history disagree, believe the higher number.* That is a business decision embedded in code — a stockout costs more than an over-flag.

**2. The thresholds are asymmetric.**

```python
# backend/app/services/risk_engine.py:50-56
def compute_risks(
    demand, inventory,
    stockout_ratio_threshold: float = 1.15,   # flag when demand > 115 % of supply
    overstock_weeks_threshold: float = 10.0,  # flag only above 10 weeks of cover
    trend_overstock_max: float = 0.92,        # …AND only if demand is softening
)
```

Stockout needs one condition (a 15 % buffer). Overstock needs **two** simultaneous conditions — high cover *and* a falling trend. The system is intentionally trigger-happy about running out and cautious about calling something dead stock.

**Why the timing matters most.** The evaluation output shows model error is concentrated exactly in the commercially critical weeks:

| Test week (2024) | WMAPE | What is happening |
|---|---|---|
| 2024-10-21 | **6.93 %** | quiet pre-season |
| 2024-11-04 | 12.63 % | build-up begins |
| 2024-11-18 | 20.29 % | pre-Black-Friday ramp |
| **2024-11-25** | **27.50 %** | Thanksgiving + Black Friday + Cyber Monday |
| 2024-12-09 | 8.67 % | post-peak lull |
| 2024-12-23 | 21.69 % | Christmas |
| 2024-12-30 | 27.15 % | New Year |

*Source: `ws_model/test_results/metrics_by_week.csv`*

Seven-percent error in a quiet October week is worth very little. Twenty-seven percent error in Black Friday week is where the money is. **This table is the strongest single artefact in your project for a business-impact conversation** — it proves you measured error where it counts rather than reporting one flattering aggregate.

---

### 2.3 Why this problem matters

- **Peak concentration.** The data generator encodes a Q4 multiplier of 1.3 / 1.8 / 2.5 for October / November / December (`model1_script.py:274`). Under that structure, December demand is 2.5× a baseline month — so a fixed percentage error in December costs 2.5× the units of the same error in July.
- **Lead times exceed the forecast horizon.** Synthetic lead times are 35–75 days (`build_case_study_tables.py:91`). You must commit inventory *before* you can observe the demand it serves. This is the structural reason forecasting exists at all — and the reason `expected_demand_in_lead_time = run_rate × lead_time` is the core risk quantity (`risk_engine.py:77`).
- **Social spikes are faster than replenishment.** MODEL2's horizons stop at 96 hours (`artifacts.py:10-16`). A campaign spike resolves in four days; a purchase order takes 35–75. So the only actionable response to a predicted spike is *reallocation between warehouses or expediting*, not new supply — which is precisely why the simulator exposes `extra_on_order` and `lead_time_delta_days` (`schemas.py:18-22`) rather than "order more."
- **Localisation.** The city model shows a 36 % spread in mean uplift between the strongest and weakest city (City_B 3.53 vs City_C 2.60, `notebooks/conti.ipynb` cell 1 output). Treating markets as interchangeable systematically misallocates stock.

---

### 2.4 Why ML is appropriate (and where it honestly isn't)

#### The case *for* ML — grounded in your own feature-importance file

```
ws_model/feature_importance.csv  (top 11 of 51)

lag_365                  0.30242   ██████████████████████████████
rolling_7                0.15892   ████████████████
holiday_pipeline         0.06587   ███████
bfcm_overlap             0.04962   █████
cybermonday_post_decay   0.04570   █████
month                    0.04231   ████
cybermonday_pre_decay    0.03122   ███
christmas_post_decay     0.02964   ███
christmas_pre_decay      0.02710   ███
blackfriday_post_decay   0.02441   ██
weddingseason_post_decay 0.02374   ██
```

Four arguments follow directly from that distribution:

1. **The signal is genuinely multi-source.** Yearly memory (`lag_365`), short memory (`rolling_7`), and ~14 event-decay/overlap features all carry non-trivial weight. A pure time-series method (ARIMA, exponential smoothing) has no natural way to ingest 44 exogenous regressors per row.
2. **The interactions are explicit and non-linear.** `bfcm_overlap` is the *product* of two decay curves (`model1_script.py:645-648`) and ranks 4th. `holiday_pipeline` is a normalised *sum* of three (`:652-656`) and ranks 3rd. Hand-writing these interaction rules for 11 events × 3 brands × 11 categories is combinatorially hopeless; a tree ensemble discovers the thresholds itself.
3. **Effects are conditional, not global.** Wedding Season affects only WS and PB brands; Back to College only PB; Labor Day only WE and PB (`model1_script.py:124-134`). A tree naturally learns "if brand_enc = 1 and backtocollege_pre_decay > 0.4 then…". Linear models would need every interaction term specified in advance.
4. **The relationship is monotone-but-not-linear.** The city model's own target rule is piecewise: zero below a velocity of 0.03, linear from 0.03 to 0.08, then *quadratic* above 0.08 (`conti_script.py:108-115`). Gradient-boosted trees approximate that with splits; a linear model cannot.

#### The case *against* — the honest caveats you must volunteer

| Caveat | Evidence | How to say it |
|---|---|---|
| **The target is a known deterministic generator plus noise.** `units_sold = base × seasonality × event_effect × dow × yoy × N(1, 0.08)` | `model1_script.py:310-315` | "The model is recovering a rule I wrote, so R² of 0.88 measures how well GBDT inverts a synthetic function — it is not evidence of real-world accuracy. On real data I'd expect materially worse, and I'd want a naive seasonal-lag baseline as the comparison." |
| **No naive baseline was ever computed.** Nothing in the repo compares the model to "predict `lag_365`" or "predict `rolling_7`". | absence in `model1_script.py:957-1038` | "The biggest gap in my evaluation is a naive benchmark. With `lag_365` at 30 % importance, a seasonal-naive forecast could be surprisingly strong, and I can't currently prove the model beats it." |
| **The influencer target is analytically defined.** `lift_t = peak_lift × exp(−λ·t/24) + ε` | `notebooks/MODEL2_ML.ipynb` cell 0, `compute_lift_curve` | "The five horizon models are learning an exponential decay whose parameters I generated. In production I'd predict `peak_lift` and `λ` only, then compute the curve in closed form — which is what the API actually needs anyway." |
| **The city model has 2,700 rows and 11 features.** | `data/luxury_surge_dataset.csv` (2,700 rows) | "That's small. With 700 trees at depth 10 on 2,160 training rows, LightGBM logs 'no further splits with positive gain' repeatedly — the model is over-parameterised for the data." |
| **Deterministic rules beat ML for the risk layer.** | `risk_engine.py:84-93` | "Risk classification is thresholds, not a model — deliberately. Buyers need to know *why* a SKU is flagged, and 'demand in lead time exceeds supply by 15 %' is auditable in a way that a classifier's probability is not." |

That last row is important. Knowing **where not to use ML** is a senior signal, and you have a concrete example of it in your own code.

---

### 2.5 Expected users

The codebase never names a user, so these are **inferred from the domain vocabulary in the code** — flagged as inference, with the evidence that supports each:

| Persona | What they use | Evidence in code |
|---|---|---|
| **Inventory / demand planner** (primary) | Risk register, KPI cards, what-if simulator | `weeks_of_cover`, `expected_demand_in_lead_time`, `lead_time_days`, `on_order`, `stock_on_hand` (`risk_engine.py:112-121`); simulator inputs `extra_on_order`, `lead_time_delta_days` (`schemas.py:21-22`) |
| **Merchandising buyer** | Weekly brief | The response title is literally `"Weekly buyer brief"` (`brief.py:47`); bullets are written in buyer language: *"~N units needed in Xd lead window vs Y available"* (`brief.py:27-29`) |
| **Marketing / campaign planner** | Forecast Agent page | Inputs are influencer id, followers, engagement rate, platform (`DemandForecastPage.tsx:215-218`); output is a 96-hour lift curve |
| **Executive / demo audience** | Dashboard KPI strip | Four aggregate counters, no drill-down (`main.py:264-269`); header reads *"Williams-Sonoma style demo"* (`App.tsx:281`) |

**Not implemented in the current codebase:** user accounts, roles, permissions, personalisation, multi-tenancy, or any per-user state. Every visitor sees identical data.

---

### 2.6 Inputs

#### Path A — dashboard inputs (files on disk)

| File | Columns | Produced by | Consumed by |
|---|---|---|---|
| `analytics/demand_with_predictions.csv` | `date, sku_id, brand_id, category` + 50 features + `units_sold` + `predicted_units` | `build_case_study_tables.py:245-250` | `tables.load_demand_predictions:20` |
| `ws_demand_dataset/ml_ready_data.csv` | same, minus `predicted_units` | `model1_script.py:803` | fallback loader `tables.load_sales_fallback:25` |
| `data/inventory.csv` | `sku_id, warehouse_id, stock_on_hand, on_order, lead_time_days` | `build_case_study_tables.py:96-104` | `tables.load_inventory:37` |
| `data/signals.csv` | `date, sku_id, signal_type, volume, source` | `build_case_study_tables.py:145-161` | `tables.load_signals:41` |
| `analytics/influencer_metrics.json` | `{targets:{t:{rmse,mae,n}}, best_models:{t:classname}}` | `build_case_study_tables.py:198-208` | `tables.load_influencer_metrics:49` |
| `analytics/influencer_sample.csv` | first 2,000 rows of features + `peak_lift_pct_pred` | `build_case_study_tables.py:223-225` | `tables.load_influencer_sample:45` |
| `analytics/sales_timeseries.csv` | `date, sku_id, units_sold, category, brand_id, store_id` | `build_case_study_tables.py:68-71` | **written but never read by the API** |

That last line is a real finding: `sales_timeseries.csv` is generated on every ETL run and no endpoint consumes it. `config.py:39-40` defines `sales_timeseries_path()` and nothing calls it. Dead output.

#### Path B — forecast agent inputs (HTTP request body)

```jsonc
POST /api/demand/forecast
{
  "product_id":      "SKU-WS-001",   // string, required
  "city":            "Mumbai",       // string, required
  "date":            "2026-08-03",   // "YYYY-MM-DD", required
  "campaign_active": true,           // bool, default false
  "influencer": {                    // optional object
    "id":              "INF-42",
    "followers":       250000,
    "engagement_rate": 0.048,
    "platform":        "instagram"
  }
}
```
*Contract: `backend/app/schemas.py:50-62`. Frontend defaults: `DemandForecastPage.tsx:211-218`.*

**How much of that input actually reaches a model — the uncomfortable truth:**

| Request field | Reaches MODEL1? | Reaches MODEL2? | Reaches MODEL3? | Evidence |
|---|---|---|---|---|
| `date` | ✅ month, dow, week, quarter, is_weekend, is_q4, day_of_month | ❌ | ✅ day_of_year, month | `demand_agent.py:36-43`, `:96-97` |
| `city` | ❌ (only via `_get_profile`, which MODEL1 never uses) | ❌ | ✅ income, home price, affordability, velocity, city dummies | `demand_agent.py:98-112` |
| `product_id` | ✅ `brand_enc` (prefix rule), `category_enc` (`hash % 10`) | ❌ | ❌ | `demand_agent.py:34-35` |
| `followers` | ❌ | ✅ mapped to feature index 0 as `log10(f)/7` | ❌ | `demand_agent.py:74, 78` |
| `engagement_rate` | ❌ | ✅ feature index 1, `× 10` | ❌ | `demand_agent.py:79` |
| `platform` | ❌ | ✅ feature index 2, binary `== "instagram"` | ❌ | `demand_agent.py:80` |
| `influencer.id` | ❌ | ❌ — used **only** as an on/off gate | ❌ | `demand_agent.py:150` |
| `campaign_active` | ❌ | ✅ gate | ❌ | `demand_agent.py:150` |

So of eight request fields, **three influencer attributes drive three of the ~19 MODEL2 features**; the remaining 16 are filled with `(hash(col) % 100)/100` (`demand_agent.py:84`). Know this cold — "what does the model actually see?" is a standard probe.

---

### 2.7 Outputs

```
┌─ POST /api/demand/forecast ────────────────────────────────────────────┐
│ {                                                                      │
│   "final_demand": 187.42,                    ← baseline + lift + city   │
│   "breakdown": {                                                        │
│     "baseline": 152.10,                      ← MODEL1                   │
│     "influencer_lift_units": 30.42,          ← baseline × pct/100       │
│     "city_growth_units": 4.90                ← MODEL3                   │
│   },                                                                    │
│   "uplift": {                                                           │
│     "enabled": true,                                                    │
│     "peak_lift_pct": 20.0,                   ← MODEL2 peak_lift_pct     │
│     "lift_curve": [ … 5 values … ],          ← MODEL2 lift_6/24/48/72/96│
│     "decay_lambda": 0.3142                   ← MODEL2 decay_lambda      │
│   },                                                                    │
│   "insights": ["Baseline demand synthesized from XGBoost signals.", …]  │
│ }                                                                       │
└────────────────────────────────────────────────────────────────────────┘
   schemas.py:65-83 · values assembled at demand_agent.py:195-209
```

| Endpoint | Output | Decision it supports |
|---|---|---|
| `/api/kpis/dashboard` | `stockout_skus`, `overstock_skus`, `signal_spikes`, `total_inventory_skus` | "Is anything on fire today?" |
| `/api/risk/skus` | ranked list with `severity`, `weeks_of_cover`, `expected_demand_in_lead_time`, `reasons[]` | "Which positions do I act on first?" |
| `/api/brief/weekly` | title, summary paragraph, ≤12 bullets | "What do I tell the team on Monday?" |
| `/api/simulate` | 14 `{day, projected_stock}` points + `assumptions[]` | "If I expedite, do I still run out?" |
| `/api/demand/forecast` | composed demand + 3-way attribution + lift curve | "How many units for this launch, and how much is the campaign worth?" |
| `/api/health` | 8 booleans/counters + messages | "Is the system actually wired up?" |

Two output-design decisions worth praising in an interview, because they are genuinely good:

1. **Every risk row carries `reasons[]` — a human-readable justification** (`risk_engine.py:87-89`, `:93`). The system never says "trust me"; it says *"projected demand during lead time exceeds available supply"* and, if applicable, *"recent demand trend is rising."*
2. **Every forecast carries `insights[]`, including failure disclosure.** When a model is missing the response literally contains `"⚠️ Baseline using fallback (Model 1 not loaded)."` (`demand_agent.py:143`). The consumer is told the number is degraded.

Explainability is a real interview topic and you have two concrete, shippable mechanisms for it — not SHAP plots in a notebook, but justification strings in the production payload.

---

### 2.8 Constraints

| Constraint | Evidence | Consequence in the design |
|---|---|---|
| **No real data available.** Hackathon context — `docs/WSI-AITHON_Particpant_Idea_submission_template (1).pptx` | Every dataset is generated: `model1_script.py:296-331`, `conti_script.py:65-147`, `MODEL2_ML.ipynb` cell 0, `build_case_study_tables.py:129-165` | Metrics measure recovery of a known generator, not real-world skill. |
| **Must run on a laptop, CPU only.** | `requirements.txt` has no torch/tensorflow; artifacts total ≈ 3.8 MB | Tree ensembles chosen over deep learning for the serving path. |
| **Must load without heavy optional deps.** | `requirements.txt:13` comment: *"Optional: only if MODEL2 … were saved by CatBoost — pip install catboost"*; `seed_and_train_influencer_demo.py:9` *"Uses sklearn only (no CatBoost) so backend loads without extra pip installs"* | The shipped MODEL2 bundle is `HistGradientBoostingRegressor`, not the notebook's CatBoost. **This constraint is the direct cause of the artifact mismatch flagged in §1.6.** |
| **Pickle/version coupling.** | `requirements.txt:11-13` pins `scikit-learn>=1.3,<2`, `xgboost>=2,<4`, `lightgbm>=4,<5`; `artifacts.py:36-38` catches `ModuleNotFoundError` explicitly | Unpickling requires the training library at the same major version — a fragility you should name before being asked. |
| **Demo must never crash.** | `artifacts.py` returns `None` + message rather than raising; `tables._read_csv:11-17` swallows all exceptions | Graceful degradation everywhere; the cost is silent wrong answers with HTTP 200. |
| **Frontend deploys to Vercel; backend does not.** | `vercel.json` (root + frontend) only builds `frontend/` | **Backend deployment is not implemented in the current codebase** — no Dockerfile, no Procfile, no host config. |
| **Analytics artifacts are git-ignored.** | `.gitignore`: `ws_demand_dataset/`, `models/*.pkl`, `ws_model/*.pkl`, `analytics/`, `data/inventory.csv`, `data/signals.csv` | A fresh clone shows the `EmptyState` screen until four scripts are run in order (`README.md` §2). |
| **Single process, in-memory model state.** | `main.py:25-33` | No shared cache across workers, no hot model reload. |

**One documentation inconsistency to fix before you interview:** `README.md` badges and clone instructions point at `github.com/studentanush/Cummins_Hackathon`, while the actual git remote is `github.com/AyushShevde/SurgeAI.git`. If a recruiter clicks the README badge it 404s or lands on a different repo. Cheap fix, avoidable embarrassment.

---

### 2.9 Success criteria

#### What the code actually measures

```
MODEL 1 — selection metric is WMAPE (lowest wins)
          scripts/model1_script.py:1050   best_name = results_df["WMAPE"].idxmin()

          WMAPE = Σ|y − ŷ| / Σ|y| × 100            model1_script.py:938-941

          Why WMAPE and not MAPE: MAPE explodes on low-volume SKUs (dividing by
          units_sold = 1) and weights a 1-unit SKU the same as a 300-unit SKU.
          WMAPE weights by volume, so high-revenue SKUs dominate the score —
          which is what a buyer cares about.

┌───────────────┬────────┬────────┬────────┬────────┐
│ Model         │ WMAPE  │  RMSE  │  MAE   │   R²   │
├───────────────┼────────┼────────┼────────┼────────┤
│ Random Forest │ 18.91  │  42.13 │  19.81 │ 0.8060 │
│ XGBoost   ★   │ 16.06  │  32.81 │  16.82 │ 0.8823 │
│ LightGBM      │ 17.83  │  38.80 │  18.68 │ 0.8354 │
└───────────────┴────────┴────────┴────────┴────────┘
  ws_model/model_comparison.csv  ·  test = 2024-10-01 → 2024-12-31, n = 2,760

  Note: the script's own header comment predicts "LightGBM ← expected winner"
  (model1_script.py:872). XGBoost won. Selection was empirical, not assumed.
```

**Extended MODEL1 diagnostics** — this is where your evaluation is genuinely above internship-average:

| Diagnostic | File | Headline result | What it proves |
|---|---|---|---|
| Overall metrics | `test_results/metrics_overall.json` | WMAPE 16.06 %, R² 0.8823, **bias +0.23 units/row**, P90 abs error 43.1 | Near-zero bias — the model isn't systematically over- or under-forecasting |
| By brand | `metrics_by_brand.csv` | PB 15.71 %, WE 16.25 %, WS 16.28 % | No brand is being neglected |
| By category (11) | `metrics_by_category.csv` | best Cutlery 14.58 %, worst Serveware 17.38 % | 2.8 pp spread — stable across the assortment |
| By SKU (30) | `metrics_by_sku.csv` | — | Per-SKU accountability |
| By week (14) | `metrics_by_week.csv` | 6.93 % → 27.50 % | **Error concentrates in peak weeks** (§2.2) |
| Event-window | `event_window_accuracy.csv` | Black Friday window 24.71 % vs normal 12.63 %; bias **−12.02** | The model **under-forecasts** the BF window by 12 units/row |
| Calibration (deciles) | `calibration.csv` | ratios 0.989 – 1.023 across all 10 deciles | Predictions are well-calibrated at every volume level |
| Residuals | `residuals.csv` | 2,760 rows, per-row error | Enables any further slice |

The Black Friday row deserves emphasis. `event_window_bias = −12.02` means: in the 14 days before through 3 days after Black Friday, the model predicts **12 units per row fewer** than actual. Under-forecasting the single highest-demand window is the worst possible direction of error — and your own evaluation caught it. Presenting a flaw *your own harness detected* is far stronger than presenting a clean number.

```
MODEL 2 — selection metric is mean OOF RMSE across TimeSeriesSplit(n_splits=3)
          notebooks/MODEL2_ML.ipynb cell 3

  Target          Winner      RMSE      R²      MAE
  ─────────────── ────────── ──────── ──────── ────────
  lift_6h         catboost     0.1115   0.9369   0.0878
  lift_24h        catboost     0.0914   0.9220   0.0718
  lift_48h        catboost     0.0748   0.8931   0.0589
  lift_72h        catboost     0.0629   0.8582   0.0488
  lift_96h        catboost     0.0557   0.8117   0.0429
  peak_lift_pct   xgboost     11.6183   0.9447   9.1852
  decay_lambda    lightgbm     0.0261   0.9307   0.0209

  Read the R² column top-to-bottom: 0.937 → 0.812. Predictability decays with
  horizon — 6 hours out is far easier than 96 hours out. That is exactly what
  you would expect and is worth pointing out as a sanity check that passed.

  ⚠ These numbers belong to the NOTEBOOK models. The bundle the API loads is
    the sklearn demo (models/*_features.json = demo_feat_0…17 + ws_flag).
    Never quote these as "my deployed model's accuracy". See §1.6 issue #3.

MODEL 3 — chronological 80/20 split, 2,160 train / 540 test
          RMSE 2.2173   MAE 1.5853   R² 0.7571        notebooks/conti.ipynb cell 2

  Plus four behavioural checks the notebook runs beyond the headline metrics:
    · category effect   actual 3.29 vs pred 3.07 (Luxury) ; 2.08 vs 1.76 (Standard)
    · high-velocity     actual 5.75 vs pred 5.02  → captures the surge regime
    · manual spike test velocity 0.25 → predicted uplift 14.17 units
    · feature ranking   rolling_units_30d 4402 > income_velocity_30d 3584 > day_of_year 2603
```

#### The LSTM benchmark — your best "engineering judgement" story

```
notebooks/MODEL1_LSTM.ipynb

  Dataset scaled up specifically for deep learning : 600 SKUs, 2020-2024,
                                                     1,096,200 rows
  Tensors                                          : X_train (1,023,000, 30, 26)
  Architecture  LSTM(64, return_sequences) → Dropout(0.2)
              → LSTM(32) → Dropout(0.2) → Dense(16, relu) → Dense(1)
              36,257 trainable params, Adam, MSE, EarlyStopping(patience=5)
  Training      6 epochs × ~420 s ≈ 42 minutes, stopped early (val_loss rose
                after epoch 1: 5.5066e-04 → 6.7264e-04)

  RESULT        WMAPE 45.81 %   RMSE 105.72   MAE 67.35
  vs XGBoost    WMAPE 16.06 %   RMSE  32.81   MAE 16.82

  → 33× more data, 42 minutes of training, and the LSTM was ~2.9× worse.
```

This is the single most valuable narrative in your project. It demonstrates that you (a) tried the fashionable approach, (b) measured it honestly, (c) scaled the data specifically to give it a fair chance, and (d) chose the simpler model on evidence. Chapter 5 covers *why* trees win on tabular event-driven data; memorise the numbers now.

#### Success criteria that are **not implemented in the current codebase**

- No business KPI: no service level, fill rate, inventory turns, gross-margin-return-on-inventory, or cost-of-error function anywhere.
- No naive/seasonal baseline for comparison.
- No prediction intervals or uncertainty quantification — every output is a point estimate.
- No A/B test, backtest harness over rolling origins, or online evaluation.
- No monitoring: no drift detection, no logging of predictions, no alerting.
- No acceptance thresholds — nothing in the code says "ship if WMAPE < X".
- No latency or throughput SLO.

---

### 2.10 Chapter 2 flowchart — problem to metric

```
   BUSINESS PAIN                MODELLED AS              MEASURED BY
   ─────────────                ───────────              ───────────

   "We under-buy before   ┌──► MODEL 1                ┌──► WMAPE 16.06 %
    peak and over-buy     │    XGBoost, 50 feats      │    by week / brand /
    after"                │    target: units_sold     │    category / SKU
                          │                           │    event-window bias
                          │                           └──► calibration deciles
   "A viral post moves    ├──► MODEL 2
    demand faster than    │    7 regressors            ───► OOF RMSE per target
    we can react"         │    targets: lift curve         R² 0.94 → 0.81
                          │            + peak + λ          (decays with horizon)
   "Bangalore ≠ Kolkata"  ├──► MODEL 3
                          │    LightGBM, 11 feats      ───► RMSE 2.22, R² 0.757
                          │    target: extra_units          + behavioural checks
                          │
   "Which SKU do I fix    ├──► RISK RULES              ───► stockout / overstock
    first?"               │    thresholds, not ML           counts + severity
                          │
   "What if I expedite?"  └──► DRAWDOWN LOOP           ───► 14-day projected stock
                               deterministic                (⚠ replays history)
```

---

### 2.11 Key Takeaways

- The project decomposes demand into **baseline + campaign spike + macro drift**, and models each at its natural grain because no joined dataset exists across the three.
- Inventory error is **asymmetric**, and the risk engine encodes that asymmetry deliberately: `max(actual, predicted)` run-rate, a 1.15 stockout ratio vs a two-condition overstock rule.
- ML is justified by **44 exogenous features, explicit interaction terms, conditional brand/category effects, and a piecewise-nonlinear target** — not by "demand forecasting is an ML problem."
- ML is **not** used for risk classification, and that is a defensible choice (auditability for buyers).
- Success is measured with **WMAPE as the selection metric**, plus eight diagnostic slices including per-week error and decile calibration.
- The evaluation harness caught a real weakness: **−12 unit/row under-forecast in the Black Friday window**. Lead with this, don't hide it.
- The **LSTM lost decisively** (45.81 % vs 16.06 % WMAPE on 1.1M rows). That is a strength of the project, not a failure.
- All data is synthetic; no business KPI, naive baseline, uncertainty estimate, or monitoring exists. **Not implemented in the current codebase.**

---

### 2.12 Revision Notes (60-second recall)

```
PROBLEM     Daily SKU demand = baseline + influencer spike + city macro drift.
            Classical forecasting misses event asymmetry, hour-scale spikes,
            and geographic heterogeneity.

WHY ML      44 exogenous features · explicit interactions (bfcm_overlap,
            holiday_pipeline) · conditional brand×category event effects ·
            piecewise non-linear target (0 / linear / quadratic at v>0.08)

WHY NOT ML  Risk classification → thresholds, for auditability
            (risk_engine.py:84-93)

USERS       demand planner (primary) · buyer (brief) · campaign planner (agent)
            No auth, no roles — inferred personas, not coded

INPUTS      Path A: 6 CSV/JSON files on disk
            Path B: product_id, city, date, campaign_active, influencer{4}

OUTPUTS     final_demand + 3-way breakdown + lift curve + insights[]
            risk rows with reasons[] · weekly brief · 14-day drawdown

KEY NUMBERS M1  WMAPE 16.06 · R² 0.8823 · bias +0.23 · P90 AE 43.1 · n=2760
            M1  RF 18.91 / XGB 16.06 / LGBM 17.83   (selected by WMAPE)
            M1  worst week 27.50 % (BF week) · best 6.93 % · BF bias −12.02
            M2  R² 0.9369 (6h) → 0.8117 (96h) · peak_lift_pct R² 0.9447
            M3  RMSE 2.2173 · MAE 1.5853 · R² 0.7571 · 2700 rows
            LSTM WMAPE 45.81 on 1,096,200 rows — 2.9× worse than XGBoost

MISSING     business KPI · naive baseline · prediction intervals · monitoring ·
            drift detection · acceptance thresholds · latency SLO
```

---

### 2.13 Common Interview Questions — Chapter 2

**Q1. "What problem does this project solve, in one minute?"**

**Ideal answer:**
"Retail demand for home goods is driven by three forces that a standard trend-and-seasonality forecast misses. First, calendar events with asymmetric windows — Christmas builds for 35 days and has a 10-day hangover, and those windows differ by brand and category. Second, influencer campaigns, which spike demand and decay within 96 hours. Third, city-level economics, where income and housing velocity change how much of a luxury category a market absorbs. I built one model per force and compose them additively, then layer a rule-based risk engine that converts the forecast into an actionable list: which SKU at which warehouse will stock out inside its lead time. The reason that last step matters is that lead times in my data are 35 to 75 days, so you have to commit inventory long before you can observe the demand it serves."

**Follow-up: "Why does a 96-hour spike matter if lead time is 50 days?"**
"It can't be met with new supply — that's exactly the point. A predicted spike is only actionable through reallocation between warehouses or expediting an existing PO, which is why my simulator exposes `extra_on_order` and `lead_time_delta_days` rather than a generic 'order more' button."

**Q2. "Why is machine learning the right tool here? Couldn't you use ARIMA or just a moving average?"**

**Ideal answer:**
"A moving average is actually a serious competitor, and I should be honest that I never benchmarked one — that's the biggest gap in my evaluation. But the feature importances argue against it: `lag_365` carries 30 % and `rolling_7` carries 16 %, so a naive method would capture roughly the memory component. The other 54 % sits in 44 exogenous features that classical time-series methods can't ingest — eleven events, each with a pre-decay and a post-decay column, plus interaction terms I engineered like `bfcm_overlap`, which is the product of the Black Friday and Cyber Monday decay curves and ranks fourth in importance. On top of that the event effects are conditional: Wedding Season only affects two of three brands, Back to College only one. A tree learns those conditions from splits; ARIMA has no mechanism for it. The strongest evidence is negative, though — I built an LSTM on 1.1 million rows and it scored 45.8 % WMAPE against XGBoost's 16.1 %. So the answer isn't 'ML is better', it's 'gradient-boosted trees on engineered features are better here, and I tested the alternatives.'"

**Common mistake:** claiming ML is needed because "the data is complex." Quantify it — 44 exogenous features, explicit interaction terms, conditional effects.

**Q3. "Who uses this, and what decision do they make with the output?"**

**Ideal answer:**
"The primary user is a demand or inventory planner. Their decision is triage: of sixty SKU-warehouse positions, which three do I act on this morning. The risk endpoint answers that directly — it returns a list sorted by severity, and every row carries a `reasons` array in plain English, like 'projected demand during lead time exceeds available supply' plus 'recent demand trend is rising.' The second user is a merchandising buyer, who gets the weekly brief — the response object is literally titled 'Weekly buyer brief.' The third is a campaign planner using the forecast agent to see how many incremental units a specific influencer would drive. I should be clear that these personas are inferred from the domain vocabulary in the code — there are no user accounts or roles; every visitor sees the same data."

**Q4. "How do you know the model is good? What's your success metric?"**

**Ideal answer:**
"WMAPE is the selection metric — weighted MAPE, sum of absolute errors over sum of actuals. I chose it over MAPE because MAPE blows up on low-volume SKUs where units sold is one or two, and it weights a 1-unit SKU identically to a 300-unit SKU. WMAPE weights by volume, which matches what a buyer cares about. XGBoost won at 16.06 % against Random Forest 18.91 % and LightGBM 17.83 %. But the aggregate is the least interesting number. My evaluation harness slices error eight ways, and two slices matter: per week, error runs from 6.9 % in a quiet October week to 27.5 % in Black Friday week — so error concentrates exactly where the revenue is. And the event-window analysis shows a bias of minus twelve units per row in the Black Friday window, meaning I systematically under-forecast the highest-demand period. That's the worst direction to be wrong in, and fixing it would be my first priority."

**Follow-up: "So how would you fix that under-forecast?"**
"Three things I'd try in order. First, sample weighting — upweight event-window rows in the loss so the model stops optimising for the 80 % of quiet days. My city model already does exactly this: it applies a weight of 3 to high-velocity rows. Second, an asymmetric loss — quantile regression at the 70th or 80th percentile instead of the mean, so the model deliberately over-forecasts where stockout cost exceeds holding cost. Third, more event-window training data — with three years I only have three Black Fridays, so the model has almost no examples of the exact regime it fails on."

**Q5. "Your R² is 0.88. Is that good?"**

**Ideal answer:**
"It's good relative to the alternatives I tested, and meaningless in absolute terms — and I'd rather say that than defend the number. Two reasons. First, the target is synthetic: I generate `units_sold` as base demand times seasonality times an event effect times a day-of-week multiplier times year-over-year growth times Gaussian noise with an 8 % standard deviation. So the model is inverting a function I wrote. An R² of 0.88 tells me GBDT recovers that structure well; it says nothing about real retail data. Second, I never computed a naive baseline. With `lag_365` at 30 % importance, 'predict what happened this day last year' might score surprisingly close, and I can't currently prove the model beats it. If I were extending this, the first thing I'd add is a seasonal-naive benchmark and report skill score relative to it rather than raw R²."

**Q6. "What are the constraints you worked under and how did they shape the design?"**

**Ideal answer:**
"Three big ones. No real data — this was a hackathon, so every dataset is generated by seeded scripts, and I'd rather state that up front than have it discovered. CPU-only laptop deployment, which is part of why tree ensembles over deep learning; the total model artifact size is under four megabytes and inference is a millisecond-scale predict call. And a dependency constraint that had a real consequence: the influencer models trained in my notebook use CatBoost, but CatBoost isn't in the backend requirements, so I wrote a fallback training script that produces sklearn-only artifacts. The result is that the bundle the API actually loads is a 19-feature demo model, not the 80-feature notebook model — and I want to be explicit that the R² of 0.94 I can quote for peak lift belongs to the notebook version, not the deployed one. That's a real gap, and the fix is either adding CatBoost to requirements or exporting to ONNX so the serving path doesn't depend on the training library."

**Q7. "If you had two more weeks, what would you do?"**

**Ideal answer:**
"In priority order. One, a feature store — persist the lag and rolling columns per SKU-date so the live forecast endpoint uses real history instead of the constant 20.0 it currently substitutes; that's the difference between my measured accuracy and my served accuracy. Two, a naive seasonal baseline and a rolling-origin backtest, so I can report skill rather than raw R². Three, prediction intervals — quantile regression at 10/50/90 — because a planner needs to size safety stock, and a point estimate can't do that. Four, fix the Black Friday under-forecast with event-window sample weighting. Five, plumbing: cache the CSV reads, vectorise the risk loop, and add tests around the risk thresholds since those are pure functions and trivially testable."

**Common mistakes to avoid on Chapter 2 questions**

| Mistake | Why it costs you |
|---|---|
| "It predicts demand using AI" | No decomposition, no grain, no target variable. Says nothing. |
| Quoting R² 0.88 without the synthetic-data caveat | An interviewer who asks "how was the target generated?" will expose it in one question. |
| Claiming the weekly brief is AI-generated | It is f-string templating (`brief.py:26-44`). The LLM version is README *roadmap*, not code. |
| Presenting only the aggregate WMAPE | You have per-week and event-window slices — using them shows evaluation maturity. |
| Hiding the LSTM result | It is your best judgement story. Lead with it. |
| Saying "success = high accuracy" | No business KPI exists in the repo; say so, then explain what you *would* measure (service level, cost of stockout vs holding). |
| Describing users you never coded for | Say "inferred from the domain vocabulary" — precision reads as honesty, not weakness. |

---

**End of Chapter 2.** Type **Continue** for Chapter 3 — Codebase Walkthrough (every important file: purpose, classes, functions, execution flow, dependencies, design decisions).
