# Chapter 14 — Resume Claim Audit (SurgeAI / Project 1)

Every claim in resume bullet order, checked against the code. Verdicts: ✅ Supported · ⚠ Partially supported / overstated · ❌ Not in code.

## 14.1 Verdict summary

| # | Claim fragment | Verdict |
|---|---|---|
| 1a | "fusing three ML models" | ✅ |
| 1b | "XGBoost seasonal baseline" | ✅ |
| 1c | "influencer-signal uplift model" | ⚠ shipped model ≠ notebook model |
| 1d | "LightGBM model driven by city-level economic indicators (housing and income data)" | ⚠ data is synthetic, not real |
| 1e | "from external physical signals" | ⚠ vague; all signals synthetic |
| 2a | "risk register that flags SKUs for stockout or overstock" | ✅ |
| 2b | **"using lead-time demand volatility"** | ❌ **no volatility computed anywhere** |
| 2c | "and current inventory levels" | ✅ |
| 3 | **"multi-agent 'Bundle & Flush' strategy… recover frozen capital"** | ❌ **entirely absent from the codebase** |
| 4a | "FastAPI REST layer with a React dashboard" | ✅ |
| 4b | "what-if simulations" | ✅ |
| 4c | **"projected impact of an influencer campaign on 14-day inventory drawdown"** | ❌ simulator has no campaign input |
| 4d | "plain-language decision briefs for managers" | ✅ |
| — | Tech list: Python, Scikit-Learn, XGBoost, LightGBM, FastAPI, React | ✅ all present |

## 14.2 The two claims that will end an interview badly

### ❌ Bullet 3 — "multi-agent 'Bundle & Flush' strategy"

**There is no such feature.** Searched the entire repo for `bundle`, `flush`, `frozen`, `capital`, `holding`, `pair`, `multi-agent`. Every hit is unrelated:

| Hit | File | What it actually is |
|---|---|---|
| `model2_bundle` | `main.py:284`, `artifacts.py:45`, `demand_agent.py:145-169` | A Python dict holding 7 uplift regressors |
| `"Essential Dorm Bedding Bundle"` | `model1_script.py:58` | A product name in the synthetic SKU catalogue |
| `try_load_model2_bundle` | `artifacts.py:45` | Artifact loader |

There is **no** logic anywhere that pairs a viral product with an overstocked one, no inventory-clearing recommendation, no holding-cost calculation, no capital-recovery metric. `risk_engine.py` classifies overstock and stops there — it produces a label and a `reasons[]` string, and nothing consumes that label to generate an action.

"Multi-agent" is also unsupported: there is one function named `run_forecast_agent` (`demand_agent.py:121`). No agent framework, no message passing, no planner, no tool loop, no second agent.

**Risk:** this is the most specific and most memorable bullet on the line. An interviewer will ask "walk me through Bundle & Flush" — it sounds like the differentiated idea. You have nothing to show, and the recovery from that moment is very hard.

**Action: delete it.** Replacement options below (§14.4) that are true and stronger.

### ❌ Bullet 2b — "lead-time demand volatility"

**Verdict: the code uses lead-time demand *level*, not volatility.** No standard deviation, variance, sigma, or safety-stock computation exists anywhere in `backend/app` or `scripts/` — grep for `volatil|.std(|variance|safety.?stock|sigma` returns **zero matches**.

What `risk_engine.py:73-93` actually computes:

```python
run_rate = max(mean_act, mean_pred)      # :76  mean, not std
expected = run_rate * lead               # :77  expected demand over lead time
woc      = stock / max(run_rate * 7, 0.01)
stockout  ⟺ expected > stock * 1.15
overstock ⟺ woc > 10.0 AND trend < 0.92
```

`_trend_ratio` (`:38-47`) is `mean(last 7d) / mean(prior 7d)` — a **direction** ratio, not a dispersion measure.

**Why this is dangerous:** "lead-time demand volatility" is a precise term of art. Anyone with supply-chain exposure hears σ over the lead-time window and expects the safety-stock formula `SS = z · σ_LT · √L`. Their first follow-up is "how did you compute σ, and what service level did you target?" You have no answer because the quantity doesn't exist.

**Action:** replace with what you actually did — which is still a legitimate and defensible design.

### ❌ Bullet 4c — "projected impact of an influencer campaign on 14-day inventory drawdown"

The simulator accepts four fields and none of them is a campaign (`schemas.py:18-22`):

```python
class SimulateRequest(BaseModel):
    sku_id: str
    warehouse_id: str = "W1"
    extra_on_order: float = 0.0
    lead_time_delta_days: int = 0
```

The influencer forecast lives on a **separate endpoint** (`POST /api/demand/forecast`) whose output never feeds `/api/simulate`. There is no wiring between them.

Two further problems with the same bullet: the 14-day series is the **last 14 historical rows** replayed (`main.py:201`, `sku_d[...].tail(14)`), and `lead_time_delta_days` is computed into the assumptions text (`:215`) but never used in the drawdown loop (`:219-223`) — the horizon is hardcoded at 14 days.

**Action:** keep "what-if simulation," change the parenthetical example to one that exists — extra purchase order and lead-time change.

## 14.3 The claims that need a caveat, not a rewrite

**1c — influencer uplift model.** Structurally true (`demand_agent.py:145-176`), but the artifacts the API loads are the sklearn `HistGradientBoostingRegressor` demo bundle trained on 18 gaussian `demo_feat_i` columns (`seed_and_train_influencer_demo.py:43-95`), not the notebook's 80-feature CatBoost/XGBoost/LightGBM models. Your tech list says "Scikit-Learn, XGBoost, LightGBM" and omits CatBoost — which is **accidentally accurate** for what ships. Keep it that way; never quote the notebook's R² 0.9447 as the deployed model's.

**1d — "housing and income data."** The phrasing implies a real dataset. `median_income` and `median_home_price` are generated by `conti_script.py:29-60` with `np.random.randint` plus a trend and spikes. The *feature design* is real and good — velocity over level, affordability ratio — but the data is not. Say "simulated city economic indicators" or "synthetic housing and income series."

**1e — "external physical signals."** Unclear phrase, and everything it could refer to (`data/signals.csv`) is synthesised at `build_case_study_tables.py:129-165`. Suggest cutting it or replacing with "external demand signals (simulated)."

## 14.4 Suggested rewrite — every word defensible

> **Agentic Supply Chain & Demand Forecasting Engine** — Python, Scikit-learn, XGBoost, LightGBM, FastAPI, React
>
> • Built (in a team) a supply-chain forecasting platform that composes three models — an XGBoost seasonal-event baseline, an influencer-uplift model predicting peak lift % and a 96-hour decay curve, and a LightGBM model on simulated city income/housing velocity — into a single demand estimate with a per-source attribution breakdown.
>
> • Engineered 50 features including 22 exponential pre/post event-decay signals across 11 retail events; selected XGBoost on **16.1 % WMAPE** (vs LightGBM 17.8 %, Random Forest 18.9 %) using a **time-based split holding out the Oct–Dec holiday quarter**.
>
> • Benchmarked a 2-layer LSTM on a **1.1M-row** sequence dataset; it scored **45.8 % WMAPE vs XGBoost's 16.1 %**, and I shipped the tree model — the engineered exogenous features and 365-day lag mattered more than sequence depth.
>
> • Built an evaluation harness slicing error by brand, category, SKU, week, event window and prediction decile, which surfaced a **−12 unit/row under-forecast inside the Black Friday window** despite near-zero overall bias.
>
> • Developed a rule-based risk register flagging stockout/overstock from projected lead-time demand vs on-hand plus on-order stock, with a plain-language justification on every row; served through FastAPI with a React dashboard offering what-if simulation (extra purchase order, lead-time change) and templated weekly decision briefs.

Every number above is in `ws_model/model_comparison.csv`, `ws_model/test_results/`, and `MODEL1_LSTM.ipynb` output. The LSTM and evaluation-harness bullets are stronger differentiators than "Bundle & Flush" ever was, because you can defend them for ten minutes.

## 14.5 Non-code items to fix before you send this out

| Item | Problem | Fix |
|---|---|---|
| **"Live Demo" link** | Only the frontend deploys (`vercel.json` builds `frontend/` only). `vite.config.ts:13-14` defaults `VITE_API_URL` to `http://localhost:8000`, so a deployed page calls the visitor's own machine and fails. A recruiter clicking it sees the red "is the backend running on port 8000?" banner. | Deploy the backend (Render/Railway/Fly), set `VITE_API_URL` in Vercel env, **or** remove the link. A broken demo link is worse than none. |
| **GitHub identity mismatch** | Resume header: `github.com/Nihar-Bapat67`. Repo remote: `AyushShevde/SurgeAI`. README badges/clone URL: `studentanush/Cummins_Hackathon`. Three identities. | Fork/mirror to your own account, fix the README badges, and point the project's "GitHub" link there. |
| **Email** | Resume shows `niharbapat15@gmail.com`; your account here is `mihirbapat15@gmail.com`. | Worth a 10-second check — a one-letter error in a contact email is unrecoverable. |
| **README claims** | README repeats "lead-time demand volatility" and describes signals as "real-time." | Fix both; interviewers read the README. |

## 14.6 Key Takeaways

- **One bullet is fabricated** ("Bundle & Flush", multi-agent) and must be deleted — nothing in the repo implements or even gestures at it.
- **Two claims are technically wrong**: "lead-time demand volatility" (no dispersion is computed) and the influencer→drawdown link (the endpoints are unconnected).
- **Everything else is supported**, and the tech stack line is accurate.
- Your strongest true material — the **LSTM benchmark** and the **8-way evaluation harness** — is currently missing from the resume while an unimplemented feature occupies a line.
- Fix the **Live Demo link** before anything else; a recruiter clicking through to an error screen costs more than any wording.

## 14.7 If you are asked about a claim you have already fixed

If an older copy of the resume is in play and someone asks about Bundle & Flush: *"That was a design we scoped during the hackathon and didn't build — the risk register classifies overstock, but nothing consumes that label to generate a bundling action. I've since taken it off my resume because I can't demo it."* Own it in one sentence and move to what you did build. Never improvise a description of code that doesn't exist — the follow-up question always arrives.

---
**End of Chapter 14.**
