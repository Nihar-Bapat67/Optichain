/**
 * Response shapes for the Control Tower API.
 * These mirror `backend/app/schemas.py` and the dict-returning routes in
 * `backend/app/main.py` — keep them in sync if the API ever changes.
 */

// ── GET /api/health ─────────────────────────────────────────────────────────
export type Health = {
  ok: boolean;
  model1_loaded: boolean;
  model2_targets_loaded: number;
  conti_model_loaded: boolean;
  demand_predictions_present: boolean;
  inventory_present: boolean;
  signals_present: boolean;
  influencer_metrics_present: boolean;
  messages: string[];
};

// ── GET /api/kpis/dashboard ─────────────────────────────────────────────────
export type Kpis = {
  stockout_skus: number;
  overstock_skus: number;
  signal_spikes: number;
  total_inventory_skus: number;
};

// ── GET /api/risk/skus ──────────────────────────────────────────────────────
export type RiskType = 'stockout' | 'overstock';

export type Risk = {
  sku_id: string;
  warehouse_id: string;
  risk_type: RiskType;
  severity: number;
  weeks_of_cover: number;
  expected_demand_in_lead_time: number;
  available_units: number;
  lead_time_days: number;
  reasons: string[];
};

export type RiskResponse = { risks: Risk[]; count: number };

// ── GET /api/brief/weekly ───────────────────────────────────────────────────
export type Brief = {
  title: string;
  summary: string;
  bullets: string[];
  stockout_count: number;
  overstock_count: number;
  signal_spikes: number;
  generated_at: string;
};

// ── GET /api/meta/skus ──────────────────────────────────────────────────────
export type SkuMeta = { sku_id: string; category: string };
export type SkuMetaResponse = { skus: SkuMeta[]; count: number };

// ── GET /api/meta/dataset ───────────────────────────────────────────────────
export type DatasetSummary = {
  data_version: number | null;
  loaded_at: string | null;
  backend: string;
  date_from: string | null;
  date_to: string | null;
  sku_count: number;
  datasets: Record<string, { rows: number; sha256: string }>;
};

// ── GET /api/demand/timeseries ──────────────────────────────────────────────
export type DemandPoint = {
  date: string;
  units_sold: number;
  predicted_units?: number | null;
};

export type DemandTimeseries = { sku_id: string; points: DemandPoint[] };

// ── GET /api/signals/timeseries ─────────────────────────────────────────────
export type SignalType = 'social' | 'search';

export type SignalPoint = {
  date: string;
  sku_id: string;
  signal_type: SignalType | string;
  volume: number;
  source?: string;
};

export type SignalTimeseries = { points: SignalPoint[] };

// ── GET /api/inventory/summary ──────────────────────────────────────────────
export type InventoryRow = {
  sku_id: string;
  warehouse_id: string;
  stock_on_hand: number;
  on_order: number;
  lead_time_days: number;
  available: number;
};

export type WarehouseSummary = {
  warehouse_id: string;
  total_available_units: number;
  sku_count: number;
};

export type InventorySummary = {
  rows: InventoryRow[];
  by_warehouse: WarehouseSummary[];
};

// ── POST /api/simulate ──────────────────────────────────────────────────────
export type SimulateRequest = {
  sku_id: string;
  warehouse_id: string;
  extra_on_order: number;
  lead_time_delta_days: number;
};

export type SimulatePoint = { day: number; projected_stock: number };

export type SimulateResponse = {
  sku_id: string;
  warehouse_id: string;
  assumptions: string[];
  points: SimulatePoint[];
  final_projected_stock: number;
};

// ── GET /api/influencer/summary ─────────────────────────────────────────────
export type TargetMetric = { rmse: number; mae: number; n: number };

export type InfluencerMetrics = {
  targets?: Record<string, TargetMetric>;
  best_models?: Record<string, string>;
};

export type InfluencerSummary = {
  metrics: InfluencerMetrics | null;
  models_loaded: string[];
  sample_rows: number;
  distribution: {
    peak_lift_pct_actual_mean: number;
    peak_lift_pct_pred_mean: number;
  } | null;
};

// ── POST /api/demand/forecast ───────────────────────────────────────────────
export type InfluencerInput = {
  id: string | null;
  followers: number | null;
  engagement_rate: number | null;
  platform: string | null;
};

export type ForecastRequest = {
  product_id: string;
  city: string;
  date: string;
  influencer: InfluencerInput;
  campaign_active: boolean;
};

export type ForecastBreakdown = {
  baseline: number;
  influencer_lift_units: number;
  city_growth_units: number;
};

export type ForecastUplift = {
  enabled: boolean;
  peak_lift_pct: number;
  lift_curve: number[];
  decay_lambda: number;
};

export type ForecastResponse = {
  final_demand: number;
  breakdown: ForecastBreakdown;
  uplift: ForecastUplift;
  insights: string[];
};
