# SurgeAI / Control Tower — ML Internship Interview Handbook

## Chapter 3 — Codebase Walkthrough

> This chapter covers **every file that matters**, in the order you should read them. For each: purpose, public surface, execution flow, dependencies, and the design decision behind it. Where a file contains a defect or dead code, it is marked ⚠ and explained — you want to find these before an interviewer does.
>
> ML *theory* is deferred to Chapters 4–8. Here we care about structure, control flow, and engineering decisions.

---

### 3.0 Recommended reading order

```
  1. config.py        ── where does everything live?
  2. schemas.py       ── what are the contracts?
  3. tables.py        ── how is data loaded?
  4. artifacts.py     ── how are models loaded?
  5. risk_engine.py   ── the only real business logic
  6. brief.py         ── thin consumer of risk_engine
  7. demand_agent.py  ── the ML composition core
  8. main.py          ── wires all of the above to HTTP
  9. scripts/*        ── how the artifacts were produced
 10. frontend/src/*   ── how a human drives it
```

`config.py` first, `main.py` late. `main.py` reads as glue once you know the pieces; read first it reads as noise.

---

## PART A — BACKEND

### 3.1 `backend/app/__init__.py` and `services/__init__.py`

Two one-line comment files (`# Supply chain analytics API`, `# Services`). They exist purely to make `app` and `app.services` importable packages, which is why the server must be started with `python -m uvicorn app.main:app` from inside `backend/` — the package root must be on `sys.path`.

**Design note:** the project uses no `src/` layout, no `setup.py`, no `pyproject.toml`. It is a script-style application, not an installable package. Fine at this size; the cost is that imports break if you launch uvicorn from the wrong directory.

---

### 3.2 `backend/app/config.py` — 73 lines

**Purpose:** single source of truth for every filesystem path and the CORS policy.

```python
# config.py:6-7
def _default_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent
#   backend/app/config.py → backend/app → backend → <REPO ROOT>

# config.py:10-31
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    project_root: Path | None = None
    data_dir: str = "ws_demand_dataset"
    ws_model_dir: str = "ws_model"
    ml_ready_file: str = "ml_ready_data.csv"
    influencer_model_dir: str = "models"
    features_engineered_file: str = "features_engineered.csv"
    analytics_dir: str = "analytics"
    case_study_data_dir: str = "data"
    conti_model_dir: str = "models"
    cors_origins: str = "*"

    def root(self) -> Path:
        if self.project_root is not None:
            return Path(self.project_root).resolve()
        return _default_project_root()

settings = Settings()          # config.py:73 — module-level singleton
```

**Structure:** 11 configurable fields, then 12 derived-path methods (`ml_ready_path`, `demand_predictions_path`, `inventory_path`, `signals_path`, `best_model_path`, `feature_cols_path`, `features_engineered_path`, `influencer_metrics_path`, `influencer_sample_path`, `conti_model_path`, `conti_features_path`, `sales_timeseries_path`) plus `cors_list()`.

**Design decisions worth defending:**

| Decision | Why it is good |
|---|---|
| Paths are **methods, not constants** | Evaluated lazily at call time, so a test can monkeypatch `project_root` and every path follows. Constants computed at import would freeze the wrong root. |
| **Every path in one class** | Zero string literals for filenames scattered across services. `tables.py` and `artifacts.py` never construct paths themselves. |
| `extra="ignore"` | Unknown env vars don't crash startup. |
| Env-overridable via `.env` | `PROJECT_ROOT`, `CORS_ORIGINS` etc. differ per environment without code changes. |
| Module-level singleton `settings` | One parse of the environment per process. |

**⚠ Defects:**

1. **Path drift.** `root()` returns the *repo root*, so `best_model_path()` = `<repo>/ws_model/best_model.pkl` and `conti_model_path()` = `<repo>/models/conti_model.pkl`. Those `.pkl` files are git-ignored. The committed copies live in `backend/ws_model/` and `backend/models/` and are **never read** under default config. On a fresh clone both models fail to load silently. (Cross-ref §1.6 issue #4.)
2. **`cors_origins: str = "*"`** combined with `allow_credentials=True` in `main.py:56` — a combination browsers reject outright, and an over-permissive default besides. The `.env.example` shows the correct value (`http://localhost:5173,http://127.0.0.1:5173`) but the code default is the wildcard.
3. **`sales_timeseries_path()` (`:39-40`) is defined and never called.** Dead API surface matching a dead output file.

---

### 3.3 `backend/app/schemas.py` — 83 lines

**Purpose:** every HTTP contract, as Pydantic v2 models. No logic.

| Model | Direction | Fields |
|---|---|---|
| `HealthResponse` | out | `ok, model1_loaded, model2_targets_loaded, conti_model_loaded, demand_predictions_present, inventory_present, signals_present, influencer_metrics_present, messages[]` |
| `SimulateRequest` | in | `sku_id, warehouse_id="W1", extra_on_order=0.0, lead_time_delta_days=0` |
| `SimulatePoint` / `SimulateResponse` | out | `day, projected_stock` / `sku_id, warehouse_id, assumptions[], points[], final_projected_stock` |
| `BriefResponse` | out | `title, summary, bullets[], stockout_count, overstock_count, signal_spikes, generated_at` |
| `InfluencerInput` | in | `id, followers, engagement_rate, platform` — **all optional** |
| `ForecastRequest` | in | `product_id, city, date` (required) `+ influencer?, campaign_active=False` |
| `ForecastBreakdown` / `ForecastUplift` / `ForecastResponse` | out | nested composition |

**Design decisions:**

- **Nested response models** (`ForecastResponse` contains `ForecastBreakdown` and `ForecastUplift`) rather than a flat dict. This forces the three-way attribution into the *type system* — you cannot return a demand number without also returning its decomposition.
- **`response_model=` on only 4 of 11 endpoints** (`health`, `brief_weekly`, `simulate`, `demand_forecast`). The other seven return raw `dict[str, Any]`, so FastAPI does no output validation and the OpenAPI schema for them is untyped. Inconsistent — an easy, credible improvement to name in an interview.
- **`date` is `str`, not `datetime.date`** (`schemas.py:60`). Pydantic would parse and validate a real date type for free; instead `demand_agent.py:28` calls `datetime.strptime(date_str, "%Y-%m-%d")`, which raises an unhandled `ValueError` → HTTP 500 on a malformed date. Using `datetime.date` would have produced a clean 422.

**⚠ Note the asymmetry:** `ForecastRequest.influencer` is optional *and* every field inside `InfluencerInput` is optional. So `{"influencer": {}}` validates fine and the gate at `demand_agent.py:150` (`influencer.get("id")`) silently disables uplift. Validation passes; behaviour changes invisibly.

---

### 3.4 `backend/app/services/artifacts.py` — 92 lines

**Purpose:** load the three model artifact groups from disk, defensively.

```python
TARGET_COLS = ["lift_6h","lift_24h","lift_48h","lift_72h","lift_96h",
               "peak_lift_pct","decay_lambda"]                      # :10-18
```

**Three functions, one uniform signature — `(object, features, messages)`:**

```
try_load_model1()        :21-42  → (model | None, list[str] | None, msgs)
    ├ checks best_model_path().is_file()  and feature_cols_path().is_file()
    ├ joblib.load both
    ├ except ModuleNotFoundError → msg "install missing lib (e.g. catboost…)"
    └ except Exception          → msg "Failed to load MODEL1: {e}"

try_load_model2_bundle() :45-69  → (dict[str, model], dict[str, list[str]], msgs)
    └ for t in TARGET_COLS:
          needs BOTH models/{t}_best.pkl AND models/{t}_features.json
          missing → `continue` (silent skip, no message)
          load failure → message, loop continues

try_load_conti_model()   :72-91  → (model | None, list[str] | None, msgs)
    └ features JSON is OPTIONAL (`if fp.is_file()`), model is not
```

**Design decisions:**

| Decision | Rationale | Cost |
|---|---|---|
| **Never raise** — return `None` + a message | The API always boots; `/api/health` reports gaps. Critical for a live demo. | Silent degradation: a fabricated `150.0` baseline is returned with HTTP 200. |
| **Explicit `ModuleNotFoundError` catch** (`:36`) | The single most likely failure is unpickling a CatBoost model without CatBoost installed. The error message names the fix. | — |
| **Per-target independence** in the MODEL2 bundle | Six of seven targets loading still yields a usable (partial) curve. | — |
| **Features stored as a per-target dict** | Different targets *could* have different feature sets. | In practice all seven are identical, so the map is redundant — and `demand_agent.py:157` exploits that by taking `list(feat_map.keys())[0]`. |
| `import json` **inside** the function (`:54`, `:80`) | No benefit here; stdlib import cost is trivial. Inconsistent with the top-level imports. | Cosmetic. |

**⚠ Silent skip:** at `:59-60`, a target whose `.pkl` or `.json` is missing is skipped with no message. `/api/health` reports `model2_targets_loaded: 4` and you have no way to learn *which* three failed. Adding one `msgs.append` line would fix it.

---

### 3.5 `backend/app/services/tables.py` — 59 lines

**Purpose:** every CSV/JSON read in the serving path.

```python
def _read_csv(path: Path, **kwargs) -> pd.DataFrame | None:   # :11-17
    if not path.is_file():
        return None
    try:
        return pd.read_csv(path, **kwargs)
    except Exception:
        return None            # ⚠ bare except, error discarded entirely
```

Six loaders sit on top of it: `load_demand_predictions`, `load_sales_fallback`, `load_inventory`, `load_signals`, `load_influencer_sample`, `load_influencer_metrics`.

**The fallback chain is the interesting bit:**

```
main._demand_frame()                                    # main.py:61-65
   ├─ tables.load_demand_predictions()   analytics/demand_with_predictions.csv
   │      has: units_sold  AND  predicted_units
   └─ if None → tables.load_sales_fallback()   ws_demand_dataset/ml_ready_data.csv
          has: units_sold only
          → injects predicted_units = NaN so downstream code sees the column
                                                        # tables.py:31-33
```

That NaN injection is deliberate and good: `risk_engine._mean_daily` checks `np.isnan(mp)` and falls back to the actual mean (`risk_engine.py:33-34`), and the frontend chart plots `predicted_units ?? null` so Recharts simply omits the line (`App.tsx:243-248`). One missing file degrades the product from "actual vs predicted" to "actual only" without a single crash.

**⚠ Three defects:**

1. **No caching.** Every request re-reads from disk. `/api/kpis/dashboard` and `/api/risk/skus` each trigger a full parse of `demand_with_predictions.csv`, and a dashboard load hits both. See Chapter 10.
2. **Bare `except Exception: return None`** — a corrupt or malformed CSV is indistinguishable from a missing one. `/api/health` will report `demand_predictions_present: True` (the file exists) while every data endpoint returns 503.
3. **No schema validation.** A CSV missing `units_sold` will pass the loader and fail deep inside `risk_engine` with a `KeyError` → HTTP 500.

---

### 3.6 `backend/app/services/risk_engine.py` — 145 lines

**Purpose:** the only substantive business logic in the backend. Converts (demand history + inventory position) into a ranked, justified risk list.

#### `RiskRow` dataclass (`:9-20`)

```python
@dataclass
class RiskRow:
    sku_id: str; warehouse_id: str; risk_type: str; severity: float
    weeks_of_cover: float; expected_demand_in_lead_time: float
    available_units: float; lead_time_days: int; reasons: list[str]
```

A typed intermediate that is converted to a plain dict at `:112-122` for JSON. Using a dataclass internally and a dict at the boundary keeps the computation type-checked without coupling the wire format to the internal shape.

#### `_mean_daily(sku_df)` (`:22-35`)

```python
tail = sku_df.sort_values("date").tail(28)          # last 28 rows ≈ 4 weeks
ma = float(tail["units_sold"].mean())
mp = float(tail["predicted_units"].mean()) if "predicted_units" in tail.columns else ma
if np.isnan(mp): mp = ma
return max(ma, 0.01), max(mp, 0.01)                 # floors prevent /0
```

Note `.tail(28)` is **28 rows, not 28 days** — correct only if the series is daily and gap-free. It is here, but that assumption is unstated.

#### `_trend_ratio(sku_df)` (`:38-47`)

```
ratio = mean(last 7 days) / mean(days −14 … −8)
  > 1 → demand rising · < 1 → falling · returns 1.0 if fewer than 15 rows
```

#### `compute_risks(...)` (`:50-124`) — the core

```
for each inventory row (sku × warehouse):
    stock     = stock_on_hand + on_order
    lead      = lead_time_days
    run_rate  = max(mean_actual, mean_predicted)        ← conservative
    expected  = run_rate × lead                          ← demand during lead time
    woc       = stock / (run_rate × 7)                   ← weeks of cover

    IF expected > stock × 1.15:
        type     = "stockout"
        severity = min(1.0, expected / max(stock,1) − 1.0)
        reasons  = ["Projected demand during lead time exceeds available supply."]
        if trend > 1.05: reasons += ["Recent demand trend is rising."]

    ELIF woc > 10.0 AND trend < 0.92:
        type     = "overstock"
        severity = min(1.0, (woc − 10) / 10)
        reasons  = ["Weeks-of-cover is high while demand is softening."]

sort by (−severity, risk_type)          ← highest severity first
return only rows where type != "ok"
```

**Design decisions:**

- **`max(actual, predicted)`** (`:76`) — when history and model disagree, believe the higher one. Encodes stockout cost > holding cost.
- **Asymmetric thresholds** — stockout needs one condition, overstock needs two (high cover **and** softening trend). Deliberate reluctance to declare dead stock.
- **`reasons[]` on every row** — the API never says "trust me." This is your explainability story, and it ships in the payload rather than living in a notebook.
- **Severity is bounded to [0,1]** by `min(1.0, …)`, making the sort stable and the UI colour-mapping simple.
- **Rules, not a classifier** — auditable, tunable without retraining, and zero labelled risk data exists anyway.

**⚠ Defects:**

1. **O(N_inventory × N_demand).** `demand[demand["sku_id"] == sku]` (`:69`) scans the full frame once per inventory row. 60 × 32,880 today; quadratic growth tomorrow. Fix: one `groupby("sku_id").tail(28).agg(...)` then merge.
2. **`max(stock, 1)` in the severity denominator** (`:86`) — for stock < 1 the severity is computed against 1, understating true severity exactly in the most extreme case.
3. **Magic thresholds as default arguments** (`1.15`, `10.0`, `0.92`) — never surfaced through `Settings`, never exposed as query params, never justified in a comment. An interviewer will ask "why 1.15?" and the honest answer is "hand-tuned so the demo shows a plausible number of flags."
4. **`_trend_ratio` uses only `units_sold`** (`:42-43`) even when `predicted_units` is available — inconsistent with `_mean_daily`, which uses both.

#### `count_signal_spikes(signals, days=7)` (`:127-145`)

```
end     = max date in signals
recent  = (end − 7d,  end]        prior = (end − 14d, end − 7d]
per-SKU mean volume in each window
spike  ⟺  recent_mean > prior_mean × 1.5  AND  recent_mean > 100
return count of spiking SKUs
```

⚠ It **does not filter by `signal_type`**, so social and search rows are averaged together (`:139-140`). Given search volume is generated as 0.4–0.9× social (`build_case_study_tables.py:142`), the mixture systematically dilutes the mean. Also `> 100` is an absolute magic constant that does not scale with SKU volume.

---

### 3.7 `backend/app/services/brief.py` — 53 lines

**Purpose:** turn the risk list into a human-readable weekly summary.

```
build_weekly_brief(demand, inventory, signals) -> BriefResponse
   risks     = compute_risks(demand, inventory)          # :16
   stockouts = [r for r in risks if type == "stockout"]  # :17
   overstocks= [r for r in risks if type == "overstock"] # :18
   spikes    = count_signal_spikes(signals)              # :19
   bullets   = top 5 stockouts + top 3 overstocks, f-string formatted  # :21-35
   if no bullets → "No critical inventory exceptions detected…"        # :36-37
   summary   = one f-string paragraph                                  # :39-43
   return BriefResponse(..., bullets=bullets[:12],
                        generated_at=datetime.now(timezone.utc).isoformat())
```

**Design decisions:**
- **Pure function of its arguments** — no I/O, no globals. Trivially unit-testable.
- **Top-5 / top-3 truncation** — a brief with 40 bullets is not a brief. Product judgement in code.
- **Empty-state string** so the UI never renders a blank card.
- **Timezone-aware UTC timestamp** (`datetime.now(timezone.utc)`, not naive `utcnow()`) — the modern, correct call.

**⚠ Say this before you are asked:** this is **f-string templating, not generative AI**. The frontend section that displays the brief sits next to a card headed "AI Insights" on the other page, and the README lists LLM narration under *roadmap*. Never let an interviewer believe an LLM wrote it.

**⚠ Duplicate work:** `compute_risks` runs here *and* in `/api/risk/skus` *and* in `/api/kpis/dashboard` — three times per dashboard load, on the same data.

---

### 3.8 `backend/app/services/demand_agent.py` — 209 lines

**Purpose:** the ML core. Synthesize feature vectors → call three models → compose.

#### Module constants (`:11-22`)

```python
CITY_PROFILES = {   # 7 cities
  "Mumbai":    {"wealth":1.2,  "luxury_sensitivity":1.4, "income":55000, "house_price":450000},
  "Delhi":     {...1.1...}, "Bangalore": {...1.3...}, "Hyderabad": {...1.15...},
  "New York":  {...1.8...}, "London":    {...1.6...}, "Dubai":     {...2.0...},
}
DEFAULT_PROFILE = {"wealth":1.0, "luxury_sensitivity":1.0, "income":40000, "house_price":300000}
LIFT_HOURS = [6, 12, 24, 48, 72, 96]
```

**⚠ Coverage gap:** the frontend offers **19** cities (`DemandForecastPage.tsx:53-57`) — Chennai, Pune, Kolkata, Ahmedabad, Jaipur, Surat, Los Angeles, Singapore, Tokyo, Paris, Sydney, Toronto are all absent from `CITY_PROFILES`. All twelve collapse to `DEFAULT_PROFILE` (`:24-25`), so **selecting Tokyo or Chennai produces byte-identical city predictions**. That is a demo-breaking bug an interviewer can trigger in ten seconds.

#### `_synthesize_m1_features(product_id, city, date_str, feature_names)` (`:27-64`)

Builds a **1-row DataFrame in the exact column order of `feature_cols.pkl`** — order matters because XGBoost binds features positionally at predict time.

```python
brand_enc = 0 if "WS" in product_id else 1 if "PB" in product_id else 2   # :34
cat_enc   = hash(product_id) % 10                                        # :35 ⚠

for col in feature_names:
    if   col == "month":            feats[col] = dt.month
    elif col == "day_of_week":      feats[col] = dt.weekday()
    elif col == "week_of_year":     feats[col] = dt.isocalendar()[1]
    elif col == "quarter":          feats[col] = (dt.month-1)//3 + 1
    elif col == "is_weekend":       feats[col] = 1 if dt.weekday() >= 5 else 0
    elif col == "is_q4":            feats[col] = 1 if dt.month >= 10 else 0
    elif col == "day_of_month":     feats[col] = dt.day
    elif col == "brand_enc":        feats[col] = brand_enc
    elif col == "category_enc":     feats[col] = cat_enc
    elif "decay"/"overlap"/"pipeline"/"spring" in col:  feats[col] = 0.0   # ⚠ :46-47
    elif "days_to" in col:                              feats[col] = 365   # ⚠ :48-49
    elif "lag"/"rolling" in col:                        feats[col] = 20.0  # ⚠ :50-51
    elif col == "trend_ratio_7_30":                     feats[col] = 1.0
    … segment/registry defaults …
    else:                                               feats[col] = 0.0
```

**⚠ This is the project's central weakness.** `lag_365` (0.302) + `rolling_7` (0.159) + all event decay/overlap columns together carry the majority of MODEL1's learned importance, and every one of them is a constant here. Also note `profile = _get_profile(city)` at `:29` is **assigned and never used** — proof in code that **city has zero effect on the baseline model**.

#### `_synthesize_m2_features(influencer, feature_names)` (`:66-86`)

```python
reach = math.log10(max(followers, 1000)) / 7.0     # :74  normalises ~1k–10M → 0.43–1.0
for i, col in enumerate(feature_names):
    if   i == 0:            data[col] = reach
    elif i == 1:            data[col] = eng_rate * 10
    elif i == 2:            data[col] = 1.0 if platform == "instagram" else 0.0
    elif col == "ws_flag":  data[col] = 1
    else:                   data[col] = (hash(col) % 100) / 100.0     # ⚠ :84
```

Positional index mapping (`i == 0/1/2`) only makes sense because the demo bundle's features are literally named `demo_feat_0…17`. Against the notebook's 80 named features this mapping is meaningless. **This function is hard evidence that the serving path was built for the demo artifacts, not the real ones.**

#### `_synthesize_conti_features(city, product_id, date_str, feature_names)` (`:88-119`)

```python
base_feats = {
  "day_of_year":        dt.timetuple().tm_yday,
  "month":              dt.month,
  "median_income":      profile["income"],
  "median_home_price":  profile["house_price"],
  "affordability_ratio":profile["house_price"] / profile["income"],
  "income_velocity_30d":0.02 * profile["wealth"],   # ⚠ synthetic constant
  "price_velocity_30d": 0.01,                       # ⚠ constant
  "rolling_units_30d":  15.0,                       # ⚠ constant
}
for col in feature_names:
    if col in base_feats:            data[col] = base_feats[col]
    elif col.startswith("city_"):    target = col.split("_")[-1]
                                     data[col] = 1 if city == target else 0   # ⚠
    elif col == "category_Standard": data[col] = 0     # always Luxury
    else:                            data[col] = 0.0
```

**⚠ The city dummies never fire.** `conti_features.json` contains `city_City_B` and `city_City_C`. `col.split("_")[-1]` yields `"B"` and `"C"`. The request city is `"Mumbai"` — never equal to `"B"`. So both dummies are always `0`, meaning **every request is silently treated as `City_A`, the reference level**. City differentiation survives only through `median_income` / `median_home_price` / `affordability_ratio` / `income_velocity_30d`, and only for the 7 cities in `CITY_PROFILES`.

Note also: `income_velocity_30d` is `rolling_units_30d`'s only companion signal, and `rolling_units_30d` is the **most important feature in MODEL3** (importance 4402, `notebooks/conti.ipynb` cell 2 output) — pinned to the constant `15.0`.

#### `run_forecast_agent(...)` (`:121-209`)

```
insights = []

STEP 1  m1 present?  → X1 = _synthesize_m1_features(...);  baseline = m1.predict(X1)[0]
                       insights += "Baseline demand synthesized from XGBoost signals."
        else         → baseline = 150.0
                       insights += "⚠️ Baseline using fallback (Model 1 not loaded)."

STEP 2  uplift_enabled = campaign_active AND influencer AND influencer["id"]      :150
        if enabled and bundle has "peak_lift_pct":
            first_target = list(feat_map.keys())[0]        ← assumes shared schema :157
            X2 = _synthesize_m2_features(influencer, feat_map[first_target])
            peak_lift_pct = bundle["peak_lift_pct"].predict(X2)[0]
            decay_lambda  = bundle["decay_lambda"].predict(X2)[0]   ⚠ no key guard :162
            lift_curve    = [bundle[t].predict(X2)[0] if t in bundle else 0.0
                             for t in ["lift_6h","lift_24h","lift_48h",
                                       "lift_72h","lift_96h"]]      ← 5 values    :165-171

STEP 3  conti present? → city_extra_units = conti.predict(Xc)[0]   else 5.0

STEP 4  influencer_lift_units = round(baseline * peak_lift_pct/100, 2)            :192
        final_demand = round(max(0.0, baseline + influencer_lift_units
                                              + city_extra_units), 2)             :193
```

**Design decisions worth praising:**

| Decision | Why it reads as senior |
|---|---|
| **Models passed in as a dict** (`main.py:280-288`), not imported | Manual dependency injection. `run_forecast_agent` is testable with stubs; it imports neither `config` nor `artifacts`. |
| **Feature builders iterate over `feature_names`**, not a hardcoded list | Column order and membership are driven by the artifact, so retraining with new features does not break the API — unknown columns just get `0.0`. |
| **Fallbacks emit warnings into `insights[]`** (`:143`, `:176`, `:189`) | Degradation is *disclosed in the payload*, not hidden. |
| **`max(0.0, …)`** on final demand | Negative demand is nonsense; the clamp is explicit. |

**⚠ Defects (5):**

1. **Curve length 5 vs `LIFT_HOURS` length 6** — the "12h" label shows `lift_24h` and "96h" plots `0` (§1.6 #2).
2. **`bundle["decay_lambda"]` accessed without a membership check** (`:162`) while every curve target *is* guarded (`:167`). If `decay_lambda_best.pkl` is missing but `peak_lift_pct_best.pkl` is present → `KeyError` → HTTP 500.
3. **`hash()` for feature values** (`:35`, `:84`) — Python's string hash is salted per process (`PYTHONHASHSEED`), so identical requests return different predictions after a restart. **Non-determinism in a prediction service.**
4. **Unused imports:** `hashlib` (`:1`) and `numpy as np` (`:4`) are never referenced.
5. **Unused variable:** `profile` in `_synthesize_m1_features` (`:29`).

---

### 3.9 `backend/app/main.py` — 291 lines

**Purpose:** HTTP layer. Startup, middleware, 11 route handlers.

#### Startup (`:25-58`)

```python
_state: dict[str, Any] = {                                    # :25-33
    "model1": None, "feature_cols": None,
    "model2": {},   "model2_feats": {},
    "conti": None,  "conti_feats": None,
    "load_messages": [],
}

@asynccontextmanager
async def lifespan(_: FastAPI):                                # :36-48
    m,  f,   msgs   = artifacts.try_load_model1()
    m2, m2f, m2msgs = artifacts.try_load_model2_bundle()
    mc, mcf, mcmsgs = artifacts.try_load_conti_model()
    _state.update(...)
    _state["load_messages"] = msgs + m2msgs + mcmsgs
    yield                                                      # ← no shutdown work

app = FastAPI(title="Supply Chain Analytics API", lifespan=lifespan)   # :51
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list(),
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
```

**Why `lifespan` and not `@app.on_event("startup")`:** the event decorators are deprecated in modern FastAPI; `lifespan` is the supported async context-manager API and guarantees load-before-serve. Load-once-at-startup is the standard pattern for pickled models — deserialising a 1.7 MB XGBoost booster per request would dominate latency.

**⚠ Global mutable state.** `_state` is a module-level dict, so under multiple uvicorn workers each process holds its own copy with no shared invalidation. Acceptable at ~3.8 MB total, but it means "reload the model" requires a restart.

#### Endpoint inventory

| # | Method | Path | Response model | Calls |
|---|---|---|---|---|
| 1 | GET | `/api/health` | `HealthResponse` | 4 × `Path.is_file()` + `_state` |
| 2 | GET | `/api/meta/skus` | dict | `_demand_frame` → `drop_duplicates` |
| 3 | GET | `/api/demand/timeseries` | dict | `_demand_frame` + date filters |
| 4 | GET | `/api/signals/timeseries` | dict | `tables.load_signals` |
| 5 | GET | `/api/inventory/summary` | dict | `tables.load_inventory` + groupby |
| 6 | GET | `/api/risk/skus` | dict | `compute_risks` |
| 7 | GET | `/api/brief/weekly` | `BriefResponse` | `build_weekly_brief` |
| 8 | POST | `/api/simulate` | `SimulateResponse` | drawdown loop |
| 9 | GET | `/api/influencer/summary` | dict | metrics JSON + sample CSV |
| 10 | GET | `/api/kpis/dashboard` | dict | `compute_risks` **again** + `count_signal_spikes` |
| 11 | POST | `/api/demand/forecast` | `ForecastResponse` | `run_forecast_agent` |

#### `/api/simulate` (`:183-231`) — read this one closely

```python
row  = inv[(inv.sku_id == body.sku_id) & (inv.warehouse_id == body.warehouse_id)]
if row.empty: raise HTTPException(404, "SKU / warehouse combination not found.")
stock = stock_on_hand + on_order + body.extra_on_order
lead  = max(1, lead_time_days + body.lead_time_delta_days)      # :194 floor at 1

future = sku_d[sku_d["predicted_units"].notna()].tail(14)        # :201  ⚠
if not future.empty and len(future) >= 14:
    daily_demands = future["predicted_units"].tolist()
    source_note   = "Using daily variable forecasts from XGBoost model."   # ⚠ :204
else:
    run = mean of last 28 predicted (falling back to actual); if NaN/≤0 → 5.0
    daily_demands = [run] * 14

remaining = stock
for day, d in enumerate(daily_demands, 1):
    remaining = max(0.0, remaining - d)
    points.append(SimulatePoint(day=day, projected_stock=round(remaining, 2)))
```

**⚠ Two defects:**
1. **`.tail(14)` is the last 14 *historical* rows** — the simulation replays the past and labels it a forecast (`:204`). There is no future-dated data anywhere in `demand_with_predictions.csv`.
2. **`lead` is computed and injected into the assumptions text (`:215`) but never used in the loop** — the horizon is hardcoded to 14 days by `daily_demands`'s length. The UI says lead time affects the burn; the code says otherwise.

**Good decisions in the same handler:** explicit 404 for an unknown SKU/warehouse pair, a floor of `max(1, …)` on lead time, and an `assumptions[]` array that states in plain English which path was taken. That last one is the right instinct — a simulator that hides its assumptions is worse than useless.

**Cross-cutting ⚠:** every handler is `def`, not `async def`. This is **correct** — blocking pandas work runs in FastAPI's threadpool instead of stalling the event loop — but interviewers probe it, so know why.

---

### 3.10 `backend/requirements.txt` and `.env.example`

```
fastapi>=0.109,<1 · uvicorn[standard]>=0.27,<1 · python-dotenv>=1,<2
pandas>=2,<3 · numpy>=1.24,<3 · joblib>=1.3,<2
pydantic>=2,<3 · pydantic-settings>=2,<3
# Match versions used when training notebooks (adjust if pickle load fails)
scikit-learn>=1.3,<2 · xgboost>=2,<4 · lightgbm>=4,<5
# Optional: only if MODEL2 (or MODEL1) pickles were saved by CatBoost — pip install catboost
```

- `scikit-learn`, `xgboost`, `lightgbm` are **not imported by any backend module** — they are required transitively at *unpickle* time. The comment says so. Good documentation of a non-obvious dependency.
- **CatBoost is deliberately excluded**, which is why the shipped MODEL2 bundle is sklearn's `HistGradientBoostingRegressor`. This one line is the root cause of the artifact mismatch (§1.6 #3).
- `python-dotenv` is required by `pydantic-settings` for `env_file` support — not dead weight.
- No `requirements-dev.txt`, no pytest, no ruff/black. **Testing and linting are not implemented in the current codebase** on the Python side (the frontend does have ESLint).

`.env.example` documents 8 variables and correctly sets `CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173`. **⚠** its header says *"defaults assume cwd = repo root"*, which is misleading — `config.py:6-7` resolves the root from `__file__`, not from the working directory.

---

## PART B — SCRIPTS (offline plane)

### 3.11.1 `scripts/model1_script.py` — 1,462 lines

The largest file in the repo. It is **four notebook cells concatenated into one module**, each with its own imports and its own docstring. Run top-to-bottom it performs the entire MODEL1 lifecycle.

| Stage | Lines | Produces |
|---|---|---|
| 1 · Dataset generation | 1–368 | `sales_data.csv`, `product_hierarchy.csv`, `events_data.csv`, `customer_segments.csv`, `registry_data.csv` |
| 2 · Feature engineering | 371–862 | `featured_data.csv`, `ml_ready_data.csv` |
| 3 · Training + selection | 864–1262 | `best_model.pkl`, `feature_cols.pkl`, `feature_importance.csv`, `model_comparison.csv`, `model_results.png` |
| 4 · Evaluation | 1264–1462 | 8 files in `ws_model/test_results/` |

**Stage 1 highlights**
- 30 SKUs across 3 brands, hand-authored with `base_demand` and `price_tier` (`:35-73`).
- Movable-feast date maths — Thanksgiving is the 4th Thursday of November, Mother's Day the 2nd Sunday of May (`:99-115`). Real calendar logic, not hardcoded dates.
- 11 events × 3 years, each with `pre_impact_window`, `post_impact_window`, `affected_brands`, `affected_categories` (`:122-135`).
- The demand equation (`:310-315`): `base × seasonality × event_effect × dow × yoy × noise`.
- A **built-in sanity check** that prints an ASCII bar chart of monthly demand to verify Q4 dominance (`:346-352`). Verifying your own generator is good practice — say so.

**Stage 2 highlights**
- `sort_values(["sku_id","date"])` **before** any lag computation (`:447`) — the classic leakage trap, avoided explicitly with a comment.
- Rolling features use `grp.shift(1).rolling(...)` (`:463-471`) — shift *then* roll, so the current day is excluded. **This is the single most important anti-leakage detail in the project.** Be ready to explain it.
- Event decay is **vectorised with numpy** over the whole frame per event (`:588-633`), not looped per row.
- `np.maximum(pre_accum, pre_d)` (`:621`) — when two occurrences of the same event overlap, take the max rather than summing. Prevents double counting.
- Drops the first year because `lag_365` is NaN (`:734`) — an honest, necessary cost of a yearly lag.
- Ends with correlation checks proving `lag_365` > `lag_30` > `lag_7` (`:846-852`).

**Stage 3 highlights**
- Time-based split at `2024-10-01` so the test set **is** the holiday season (`:922-933`) — deliberately the hardest window, not a random 20 %.
- Custom `wmape` (`:938-941`) with a docstring explaining volume weighting.
- Three models trained with timing; selection by `results_df["WMAPE"].idxmin()` (`:1050`).
- ⚠ `eval_set=[(X_test, y_test)]` is passed to both XGBoost (`:1004`) and LightGBM (`:1032`). No early stopping is configured, so it only prints eval metrics rather than tuning — but **passing the test set as an eval set is a habit that becomes leakage the moment early stopping is enabled**. Flag it and say you'd use a separate validation split.
- ⚠ The header comment predicts *"LightGBM ← expected winner"* (`:872`). XGBoost won. The prediction was wrong and the code kept the empirical result — worth pointing out as evidence the selection was data-driven.

**Stage 4 highlights** — `metrics_dict` (`:1307-1318`) computes WMAPE, MAPE, RMSE, MAE, R², **bias**, and **P90 absolute error**, then slices by brand, category, SKU, week, event window, and prediction decile. This evaluation suite is the strongest part of the whole repository.

**⚠ Structural criticism to volunteer:** 1,462 lines in one file with four `import pandas as pd` statements, module-level side effects, and no functions wrapping the stages. It is a notebook export, not production code. The fix — split into `generate.py` / `features.py` / `train.py` / `evaluate.py` with a CLI — is obvious and cheap, and saying so shows you know the difference.

### 3.11.2 `scripts/conti_script.py` — 378 lines

Identical structure to `notebooks/conti.ipynb`. Three concatenated stages: generator (`:1-168`), EDA (`:170-210`), training + save (`:212-378`).

- Target rule (`:106-132`) is explicitly piecewise: `0` below velocity 0.03, linear 0.03–0.08, **quadratic** above 0.08; then `×1.5` for Luxury / `×0.3` for Standard; then `× luxury_sensitivity`; then `+ wealth×2`; then Gaussian noise; then clamped to `[0, 50]`.
- `pd.get_dummies(..., drop_first=True)` (`:232`) → City_A and Luxury become reference levels. **This is why `conti_features.json` contains only `city_City_B`, `city_City_C`, `category_Standard`** — and why the serving-side dummy bug (§3.8) exists.
- **Sample weighting** (`:267`): `1 + (income_velocity_30d > 0.1) * 2` — triples the loss weight on surge rows. This is the same technique you should propose as the fix for MODEL1's Black Friday under-forecast (Chapter 2, Q4 follow-up). You already used it once; say that.
- Predictions clipped to `[0, 50]` (`:280`) to match the target's clamp.
- ⚠ `matplotlib.pyplot` calls with no `plt.show()`/`savefig` in script context (`:188`, `:303`, `:309`) — figures are built and discarded outside a notebook.
- ⚠ `df` is reloaded from CSV three times (`:174`, `:224`) and `import pandas as pd` appears three times. Notebook residue.
- ⚠ `predict_uplift()` (`:359-369`) is defined and never called — dead code.
- ⚠ Writes to `"luxury_surge_dataset.csv"` and `"models/…"` **relative to the current working directory**, so it must be run from the repo root or the artifacts land in the wrong place.

### 3.11.3 `scripts/seed_and_train_influencer_demo.py` — 103 lines

Purpose is stated honestly in its own docstring (`:1-12`): *"Train a minimal MODEL2-style bundle for local demo when notebook outputs are missing… Uses sklearn only (no CatBoost) so backend loads without extra pip installs. For production, replace artifacts with outputs from MODEL2_ML.ipynb."*

- 3,500 rows × 18 `demo_feat_i` gaussian columns + `ws_flag` (`:43-49`).
- Targets built from a smooth latent `z` with a genuine interaction term `0.15·X₃·X₄` (`:52-57`), then exponential/sigmoid transforms so a GBDT has something non-trivial to fit (`:58-68`).
- One `HistGradientBoostingRegressor(max_depth=5, max_iter=120, lr=0.08)` per target, saved as `{target}_best.pkl` + `{target}_features.json` (`:82-95`).

**This file is the honest one.** It says exactly what it is. The problem is not the script — it is that its artifacts are what the API loads while the notebook's metrics are what gets quoted.

### 3.11.4 `scripts/seed_demo_ml_ready.py` — 47 lines

Emergency fallback: 3 SKUs × 120 days with `units_sold = base + 8·sin(i/18) + N(0,10)` (`:29`). Produces only `date, sku_id, brand_id, category, units_sold` — **no engineered features**. So `build_case_study_tables._predict_model1` finds missing columns and falls back to a 7-day rolling mean (`:59-62`). A deliberate, coherent degradation chain.

### 3.11.5 `scripts/build_case_study_tables.py` — 264 lines

The ETL bridge between the offline and online planes. Only script with a real CLI (`argparse --root`, `:232-235`) and a `main() -> int` returning an exit code — the most production-shaped file in the repo.

```
main()  :231-259
  ├ mkdir analytics/ and data/
  ├ _load_ml_ready()            :43-48   warn+None if missing
  ├ sort by (sku_id, date)      :244
  ├ df["predicted_units"] = _predict_model1(df, root)     :245
  │     ├ pickles missing        → 7-day rolling mean fallback   :55-56
  │     ├ feature columns missing→ 7-day rolling mean fallback   :59-62
  │     └ else  model.predict(df[feats].replace(±inf, nan).fillna(0))  :63-65
  ├ clip(lower=0)               :246   ← no negative demand
  ├ write analytics/demand_with_predictions.csv
  ├ _write_sales_ts()           :68-71  ⚠ output never read by the API
  ├ _build_inventory()          :74-126
  ├ _build_signals()            :129-165
  └ _influencer_block()         :168-228
```

- `_build_inventory` (`:74-126`) uses a **seeded** RNG (`default_rng(42)`) and then *forces* the narrative: the 2 fastest-moving SKUs get stock set to 35 % of lead-time demand (guaranteed stockout) and the 2 slowest get 120 days of cover (guaranteed overstock) (`:109-121`). **Be upfront that the risk register is staged** — it is a demo fixture, not discovered risk.
- `_build_signals` (`:129-165`) generates social and search volume per SKU-day with a sinusoidal seasonal term and multiplicative noise; `search = social × U(0.4, 0.9)`.
- `_influencer_block` (`:168-228`) scores `features_engineered.csv` with each `{target}_best.pkl`, writes RMSE/MAE/n per target plus `type(model).__name__` — which is how the dashboard displays which algorithm won each target.
- ⚠ It scores the models on the **same rows they were trained on**, so `influencer_metrics.json` reports **in-sample** error. The dashboard bar chart of RMSE is therefore optimistic. The honest CV numbers live only in the notebook output.

---

## PART C — FRONTEND

### 3.12.1 `frontend/src/lib/api.ts` — 24 lines

```ts
const base = import.meta.env.VITE_API_URL ?? '';
export async function fetchJson<T>(path: string): Promise<T> { … }
export async function postJson<T>(path: string, body: unknown): Promise<T> { … }
```

Both throw `new Error(text || res.statusText)` on `!res.ok`, so FastAPI's `HTTPException` detail reaches the UI. Generic over `T`, zero dependencies — no axios, no react-query. At 11 endpoints that is the right call.

**⚠** `vite.config.ts:13-14` sets `VITE_API_URL` to `'http://localhost:8000'` via `define` whenever the env var is unset — which **overrides the dev proxy**, since `base` is then non-empty and requests go cross-origin instead of through `/api`. The proxy at `:8-10` is effectively bypassed in the default dev setup, which is precisely why CORS has to be permissive.

### 3.12.2 `frontend/src/types.ts` — 34 lines

Five types: `Health`, `Kpis`, `Risk`, `Brief`, `SkuMeta`. Hand-written to mirror `schemas.py`.

**⚠ Drift:** `Health` is missing `conti_model_loaded`, which the backend returns (`schemas.py:10`). TypeScript ignores extra runtime fields, so nothing breaks — but the UI cannot display Model 3's load status, and `App.tsx:535` only ever shows `model2_targets_loaded`. Two hand-maintained copies of one contract is the underlying problem; generating types from the OpenAPI schema (`openapi-typescript`) removes the class of bug entirely. Good improvement to propose.

### 3.12.3 `frontend/src/main.tsx` — 9 lines

Standard React 19 root: `createRoot(...).render(<StrictMode><App /></StrictMode>)`. Imports `./index.css` only.

**⚠ `App.css` is never imported by anything** — and its contents are pure Vite scaffold (`.counter`, `.hero`, `#next-steps`, `#docs`, `.ticks`). **Dead file, 3 KB.** Likewise `index.html` links `<link rel="icon" href="/vite.svg">` while `public/` contains `favicon.svg` and `icons.svg` and no `vite.svg` — **broken favicon**. Both are 30-second deletions that make the repo look cared-for.

### 3.12.4 `frontend/src/App.tsx` — 563 lines

**Structure:** three local components then the default export.

| Component | Lines | Role |
|---|---|---|
| `EmptyState` | 27–51 | Setup instructions + `health.messages` when artifacts are missing |
| `KpiCard` | 53–79 | One metric tile with a tone colour |
| `RiskTable` | 83–159 | TanStack Table with sorting, default `severity desc` |
| `App` | 161–563 | State, data loading, layout, simulator |

**State:** 14 `useState` hooks (`:162-183`) — page tab, health, kpis, skus, selected sku, risks, brief, influencer summary, demand points, signal points, sim inputs ×4, sim result, error, loading.

**Data flow:**

```
useEffect(:219-221) → loadCore(:187-217)
    ① fetchJson('/api/health')
    ② if !demand_predictions_present → stop, render EmptyState        :193-196
    ③ Promise.all([ kpis, meta/skus, risk/skus, brief/weekly,
                    influencer/summary.catch(()=>null) ])              :197-203
    ④ default sku = first SKU, for both chart and simulator            :209-211

useEffect(:223-241) fires on [sku, ready]
    ⑤ /api/demand/timeseries?sku_id=…        (awaited)
    ⑥ /api/signals/timeseries?sku_id=…       (awaited, sequential)
    ⑦ filter signal_type === 'social', slice(-90)                      :234-235
```

**Design decisions:**

- **Health-gate before fanning out** (`:193-196`) — no cascade of failing requests when the backend is unconfigured. Genuinely good defensive UX.
- **`Promise.all` for the five independent calls** — one round-trip latency instead of five.
- **`.catch(() => null)` on the influencer call only** (`:202`) — that panel is optional; the other four are required. Deliberate criticality tiering.
- **`useCallback` on `loadCore`** with `[]` deps, so the mount effect does not loop.
- **Tab state instead of a router** (`:162`) — two pages; `react-router` would be dead weight. Cost: no deep links, no back button.

**⚠ Defects:**
1. Steps ⑤ and ⑥ are **sequential `await`s** (`:227-233`) despite being independent — `Promise.all` would halve that latency. Inconsistent with the good pattern used at `:197`.
2. **`alert()` for simulation errors** (`:272`) — the rest of the app renders errors inline.
3. **Client-side `.slice(-90)`** (`:235`) — the API returns the entire signal history and the browser discards most of it. Should be a `from=` query param; the endpoint already supports one (`main.py:129`).
4. **No refresh of `/api/health`** after the initial load unless the user clicks Refresh.

### 3.12.5 `frontend/src/DemandForecastPage.tsx` — 599 lines

**Structure:** local interfaces (`:18-45`), constants (`:49-57`), six presentational sub-components, then the page.

| Sub-component | Lines | Role |
|---|---|---|
| `GlowCard` | 61–69 | Glass-morphism container |
| `StatBadge` | 71–87 | Gradient metric tile |
| `InsightChip` | 89–104 | Cycles 3 icons/colours by `index % 3` |
| `BreakdownPie` | 106–156 | Recharts donut, `.filter(d => d.value > 0)` |
| `LiftCurveChart` | 158–187 | Recharts area with gradient fill |
| `Field` | 191–198 | Label + input wrapper |

**Flow:** 8 form states (`:211-218`) → `runForecast` (`:234-261`) builds a `ForecastRequest`, POSTs once, sets `result`, triggers a 2-second success toast (`:227-232`).

**Decisions:**
- **One request per click, no debounce/auto-run** — inference is explicit and cheap to reason about.
- **Influencer object is always sent**, with nulls when the campaign toggle is off (`:244-251`), so the backend contract never varies in shape.
- **Raw JSON accordion** (`:555-563`) — a `<details>` block showing the full response. Excellent for a demo: it proves the numbers came from the API rather than the UI. Point at this in an interview.
- **Empty state explains the three models** (`:580-592`) before any request is made.

**⚠ Defects:**
1. **`HOURS` has 6 entries; `lift_curve` has 5** (`:49` vs `:159`) — mislabelled x-axis, phantom `0` at 96h.
2. **12 of the 19 cities in `CITIES`** (`:53-57`) have no `CITY_PROFILES` entry, so they produce identical output.
3. **The card is headed "AI Insights"** (`:545`) while `insights[]` is a list of f-strings from `demand_agent.py`. Reword it before a demo.
4. **Local `ForecastRequest`/`ForecastResponse` interfaces** (`:18-45`) duplicated here instead of living in `types.ts` — a third hand-maintained copy of the contract.

### 3.12.6 Frontend configuration

| File | Notes |
|---|---|
| `package.json` | React 19.2, Vite 8, TS 6, `recharts` 3.8, `@tanstack/react-table` 8.21. Scripts: `dev`, `build` (`tsc -b && vite build`), `lint`, `preview`. Type-check runs as part of build — good. |
| `vite.config.ts` | React plugin, `/api` proxy → `127.0.0.1:8000`, `define` for `VITE_API_URL` (⚠ see §3.12.1). |
| `tailwind.config.js` | Custom palette: `surface` (#0f1419 / raised / border), `accent`, `danger`, `warn`, `ok`; fonts DM Sans + Outfit. A real design token set, not default Tailwind. |
| `tsconfig.app.json` | `strict` is **not** enabled, but `noUnusedLocals`, `noUnusedParameters`, `noFallthroughCasesInSwitch`, `erasableSyntaxOnly`, `verbatimModuleSyntax` are. Bundler module resolution, `jsx: react-jsx`. |
| `eslint.config.js` | Flat config: JS recommended + typescript-eslint + react-hooks + react-refresh. |
| `index.css` | Google Fonts import, Tailwind layers, two keyframe animations (`fadeIn`, `successFlash`). |
| `vercel.json` (both) | Root builds `frontend/`; frontend one adds the SPA rewrite. ⚠ **No backend deployment config anywhere.** |

---

## PART D — NOTEBOOKS

| Notebook | Cells | Relationship to scripts | Unique content |
|---|---|---|---|
| `MODEL1_XGBOOST.ipynb` | 4 | **Source of `scripts/model1_script.py`** — same 4 stages | none (script is the export) |
| `MODEL1_LSTM.ipynb` | 3 | No script equivalent | 600-SKU / 1,096,200-row generator; 30-day sliding-window tensors `(1023000, 30, 26)`; Keras LSTM(64)→LSTM(32)→Dense; **WMAPE 45.81 %** |
| `MODEL2_ML.ipynb` | 5 | Demo script is a *replacement*, not an export | 10k-post generator, 95-column feature pipeline, CatBoost/LGBM/XGB per target with `TimeSeriesSplit(3)`, SHAP importance |
| `conti.ipynb` | 5 | **Source of `scripts/conti_script.py`** | identical |

**⚠ Reproducibility gap:** MODEL2's real pipeline exists **only** as a notebook. There is no `scripts/model2_script.py`, its intermediate `training_dataset_full.csv`, `features_engineered.csv` and `scaler.pkl` are git-ignored, and the `README.md` setup instructions never mention it — they run the *demo* seeder instead. So the 80-feature CatBoost bundle cannot be reproduced from a fresh clone by following the README.

---

### 3.13 Dead code and inconsistency inventory

Worth a five-minute cleanup pass before you show anyone the repo:

| # | Item | Location |
|---|---|---|
| 1 | `App.css` — Vite scaffold, imported by nothing | `frontend/src/App.css` |
| 2 | Broken favicon (`/vite.svg` absent from `public/`) | `frontend/index.html:5` |
| 3 | `sales_timeseries.csv` written, never read | `build_case_study_tables.py:253`, `config.py:39` |
| 4 | `predict_uplift()` defined, never called | `conti_script.py:359-369` |
| 5 | Unused imports `hashlib`, `numpy` | `demand_agent.py:1, 4` |
| 6 | Unused variable `profile` | `demand_agent.py:29` |
| 7 | `conti_model_loaded` returned but absent from the TS type | `schemas.py:10` vs `types.ts:1-10` |
| 8 | README badges/clone URL point to a different repository | `README.md` header, §2 |
| 9 | Duplicate model artifacts under `backend/` that default config never reads | `backend/models/`, `backend/ws_model/` |
| 10 | Forecast types duplicated in the page instead of `types.ts` | `DemandForecastPage.tsx:18-45` |
| 11 | `pandas` imported 3–4 times per script | `model1_script.py`, `conti_script.py` |
| 12 | `matplotlib` figures created but never shown or saved in script context | `conti_script.py:188, 303, 309` |

---

### 3.14 Key Takeaways

- The backend is **five services + one HTTP module**, with a clean acyclic dependency graph and manual dependency injection of models into `demand_agent`.
- `config.py` centralises every path as a **method**, making the whole app relocatable by one env var — and the one bug that matters is that its default root points away from the committed artifacts.
- `artifacts.py` and `tables.py` share a philosophy: **never raise, return `None`, report through `/api/health`**. Great for a demo, wrong for production (200 OK on a fabricated answer).
- `risk_engine.py` is the only real business logic: conservative run-rate, asymmetric thresholds, `reasons[]` on every row. It is **rules by choice, not by limitation**.
- `demand_agent.py` is well-structured (feature builders driven by the artifact's own column list) but **its inputs are constants**, and that gap between measured accuracy and served accuracy is the thing to be honest about.
- `model1_script.py` contains the project's best work — anti-leakage `shift(1).rolling()`, vectorised event decay, holiday-season test split, and an eight-way evaluation suite — inside its worst packaging (1,462 lines, no functions, four import blocks).
- The frontend gets the important things right (health gate, `Promise.all`, criticality tiering, raw-JSON accordion) and the small things wrong (sequential awaits, `alert()`, dead CSS, 6-vs-5 chart labels).
- **Not implemented in the current codebase:** Python tests, linting/formatting config, type generation from OpenAPI, backend deployment config, a `model2` training script, request logging.

---

### 3.15 Revision Notes (60-second recall)

```
BACKEND FILES (7 that matter)
  config.py      73 ln  Settings + 12 path methods + cors_list()
  schemas.py     83 ln  9 Pydantic models; only 4/11 endpoints use response_model
  artifacts.py   92 ln  3 loaders, uniform (obj, feats, msgs), never raise
  tables.py      59 ln  6 CSV/JSON loaders on one defensive _read_csv
  risk_engine.py 145 ln RiskRow + _mean_daily + _trend_ratio + compute_risks
                        + count_signal_spikes
  brief.py       53 ln  pure function, f-strings, top-5/top-3, UTC timestamp
  demand_agent.py 209 ln 3 feature synthesizers + run_forecast_agent
  main.py        291 ln lifespan loader, CORS, 11 endpoints

SCRIPTS
  model1_script.py       1462 ln  gen(1-368) FE(371-862) train(864-1262) eval(1264-1462)
  conti_script.py         378 ln  gen + EDA + LGBM + save
  seed_and_train_influencer_demo.py 103 ln  sklearn-only MODEL2 stand-in
  seed_demo_ml_ready.py    47 ln  3 SKUs × 120 days emergency data
  build_case_study_tables.py 264 ln  ETL; only file with a real CLI

FRONTEND
  api.ts 24 · types.ts 34 · main.tsx 9 · App.tsx 563 · DemandForecastPage.tsx 599

THE 3 ANTI-LEAKAGE / QUALITY MOMENTS TO QUOTE
  1. sort_values(["sku_id","date"]) before lags        model1_script.py:447
  2. grp.shift(1).rolling(7)  — shift THEN roll        model1_script.py:463
  3. time split at 2024-10-01, test = holiday season   model1_script.py:922

THE 3 DEFECTS TO VOLUNTEER FIRST
  1. inference features are constants                  demand_agent.py:46-51
  2. conti city dummies never fire → always City_A     demand_agent.py:111-113
  3. lift_curve 5 values vs 6 axis labels              demand_agent.py:165 / Page:49
```

---

### 3.16 Common Interview Questions — Chapter 3

**Q1. "Walk me through your backend file structure and why it's organised that way."**

**Ideal answer:**
"Four layers. `config.py` owns every filesystem path as a method on a pydantic-settings class, so nothing else in the codebase constructs a path from a string literal — and because they're methods rather than constants, a test can override the project root and every path follows. `schemas.py` holds the Pydantic request and response models, so the HTTP contract is declarative and separate from logic. `services/` has five modules: two loaders — `artifacts` for models, `tables` for CSVs — and three logic modules: `risk_engine` for the threshold rules, `brief` which consumes `risk_engine`, and `demand_agent` for the three-model composition. Then `main.py` is pure glue: startup, CORS, and eleven handlers that call into services. The dependency graph is acyclic and one-directional — no service imports `main`, and `demand_agent` doesn't even import `config` or `artifacts`; the models are passed in as a dict from the handler, which is manual dependency injection and makes the composition logic testable with stub models."

**Q2. "Why do your loaders return `None` instead of raising?"**

**Ideal answer:**
"It's a deliberate trade for demo resilience. `artifacts.py` catches `ModuleNotFoundError` specifically — because the most likely failure is unpickling a CatBoost model without CatBoost installed — and generic exceptions, then returns `None` plus a human-readable message. `tables.py` does the same for CSVs. Everything collects into `/api/health`, which reports exactly what loaded and what didn't, and the frontend gates on that flag and shows a setup screen instead of firing requests that will fail. The upside is the server always boots and a judge never sees a stack trace. The downside is real and I'd change it in production: the forecast endpoint returns a fabricated 150-unit baseline with a 200 OK when Model 1 is missing. It does prepend a warning to the insights array, so it's disclosed, but a caller parsing JSON won't notice. In production I'd return 503 from `/api/demand/forecast` when a required model is absent and keep graceful degradation only for the optional dashboard panels."

**Q3. "Show me where you prevented data leakage."**

**Ideal answer:**
"Three places. First, in feature engineering I sort by SKU and date before computing any lag — line 447 — because `groupby.shift()` on an unsorted frame silently produces garbage. Second, and this is the one that matters most, the rolling features are `grp.shift(1).rolling(window=7).mean()` — shift first, then roll. If you roll first you include the current day's `units_sold` in the feature predicting that same day, which is direct target leakage and would produce a beautiful, useless model. Third, the train/test split is time-based at 2024-10-01, not random — with lag and rolling features a random split lets the model see future rows for the same SKU. And I deliberately put the test set on the holiday quarter so I'm evaluating on the hardest window rather than an easy one. One thing I'd flag against myself: I pass the test set as `eval_set` to XGBoost and LightGBM. I don't enable early stopping so it's only printing metrics, but it's a bad habit — the moment someone adds early stopping it becomes leakage, and it should be a separate validation split."

**Q4. "Which single file would you rewrite first, and how?"**

**Ideal answer:**
"`demand_agent.py`, specifically the three feature-synthesis functions. Right now `_synthesize_m1_features` fills every lag and rolling column with the constant 20.0 and every event-decay column with 0.0 — and those columns carry most of the model's learned importance, so the live endpoint doesn't inherit the accuracy I measured offline. The fix is a feature store: the ETL already computes real lag and rolling values for every SKU-date when it writes `demand_with_predictions.csv`, so I'd persist that as a lookup keyed on SKU and date and have the agent read from it. Event decays are pure calendar maths — I can compute those exactly for any date with the same function the training pipeline uses, which is the right answer anyway because it removes a duplicated implementation. For future dates beyond the history I'd need recursive forecasting, feeding each prediction back as the next day's lag. I'd also fix the city dummy bug in the same pass: `conti_features.json` has `city_City_B` and `city_City_C`, the code splits on underscore and compares the last token to the request city, so `Mumbai` never matches `B` and every request silently scores as City_A."

**Q5. "How does the frontend know the backend is healthy?"**

**Ideal answer:**
"`/api/health` returns eight booleans and counters — whether each of the three models loaded, whether each of the four data files is present, and up to twenty load messages. On mount the app fetches health first, and if `demand_predictions_present` is false it stops immediately and renders a setup component with the exact command to run, plus the backend's own messages. Only if that passes does it `Promise.all` the five data endpoints. That ordering matters: without it a misconfigured backend produces five simultaneous failures and five error toasts instead of one actionable screen. One gap I'd fix — the TypeScript `Health` type is missing `conti_model_loaded`, so the UI can display Model 2's status but not Model 3's. That's the general risk of hand-maintaining types that mirror a server contract; generating them from the OpenAPI schema would remove the whole class of bug."

**Q6. "You have 1,462 lines in one script. Defend that."**

**Ideal answer:**
"I won't defend it — it's a notebook export, and it shows: four separate `import pandas as pd` blocks, all module-level side effects, no functions wrapping the stages. It works because it's meant to be run once top-to-bottom, and keeping it as one file did mean the whole pipeline reproduces with one command. But it's not maintainable — you can't rerun training without regenerating the dataset, you can't unit-test any stage, and a failure at line 1,100 wastes the twenty minutes of work before it. The refactor is obvious: four modules — generate, features, train, evaluate — each with a `main()` and a CLI flag, with the intermediate CSVs as the contract between them, then a small orchestrator. `build_case_study_tables.py` is already shaped that way, with argparse and a `main()` returning an exit code, so the pattern exists in the repo; the training script just never got the same treatment."

**Common mistakes to avoid on Chapter 3 questions**

| Mistake | Why it costs you |
|---|---|
| Not knowing why handlers are `def` and not `async def` | Blocking pandas in `async def` stalls the event loop. `def` → threadpool → correct. Interviewers love this one. |
| Calling the weekly brief AI-generated | `brief.py` is f-strings. |
| Claiming the risk register found real risk | `build_case_study_tables.py:109-121` forces 2 stockouts and 2 overstocks. |
| Quoting `influencer_metrics.json` RMSE as validation error | It is scored in-sample on the training rows (`:195-197`). |
| Saying "the models are loaded per request" | Loaded once in `lifespan` into `_state`. |
| Being unable to name a defect in your own code | You have twelve documented in §3.13. Pick three and lead with them. |

---

**End of Chapter 3.** Type **Continue** for Chapter 4 — Machine Learning Pipeline (dataset, preprocessing, cleaning, feature engineering, embeddings, feature selection, training, validation, inference, post-processing, evaluation, serialization, deployment, error analysis, failure cases).
