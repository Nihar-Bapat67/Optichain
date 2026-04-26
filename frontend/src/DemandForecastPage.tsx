import { useState, useEffect } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { postJson } from './lib/api';

// ── Types ──────────────────────────────────────────────────────────────────

interface ForecastRequest {
  product_id: string;
  city: string;
  date: string;
  influencer: {
    id: string | null;
    followers: number | null;
    engagement_rate: number | null;
    platform: string | null;
  };
  campaign_active: boolean;
}

interface ForecastResponse {
  final_demand: number;
  breakdown: {
    baseline: number;
    influencer_lift_units: number;
    city_growth_units: number;
  };
  uplift: {
    enabled: boolean;
    peak_lift_pct: number;
    lift_curve: number[];
    decay_lambda: number;
  };
  insights: string[];
}

// ── Constants ──────────────────────────────────────────────────────────────

const HOURS = ['6h', '12h', '24h', '48h', '72h', '96h'];

const PLATFORMS = ['instagram', 'tiktok', 'youtube', 'twitter', 'facebook', 'pinterest', 'snapchat', 'linkedin'];

const CITIES = [
  'Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Chennai', 'Pune', 'Kolkata',
  'Ahmedabad', 'Jaipur', 'Surat', 'New York', 'Los Angeles', 'London',
  'Dubai', 'Singapore', 'Tokyo', 'Paris', 'Sydney', 'Toronto',
];

// ── Sub-components ─────────────────────────────────────────────────────────

function GlowCard({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-2xl border border-white/10 bg-white/5 backdrop-blur-sm p-5 transition-all duration-300 hover:border-violet-500/30 hover:bg-white/[0.07] ${className}`}
    >
      {children}
    </div>
  );
}

function StatBadge({ label, value, unit = '', color = 'violet' }: { label: string; value: number | string; unit?: string; color?: string }) {
  const colorMap: Record<string, string> = {
    violet: 'from-violet-500/20 to-violet-600/10 border-violet-500/30 text-violet-300',
    cyan: 'from-cyan-500/20 to-cyan-600/10 border-cyan-500/30 text-cyan-300',
    emerald: 'from-emerald-500/20 to-emerald-600/10 border-emerald-500/30 text-emerald-300',
    amber: 'from-amber-500/20 to-amber-600/10 border-amber-500/30 text-amber-300',
  };
  return (
    <div className={`rounded-xl border bg-gradient-to-br ${colorMap[color]} p-4 text-center`}>
      <p className="text-xs uppercase tracking-widest opacity-70 mb-1">{label}</p>
      <p className="text-2xl font-bold font-mono">
        {typeof value === 'number' ? value.toLocaleString(undefined, { maximumFractionDigits: 1 }) : value}
        {unit && <span className="text-sm ml-1 opacity-60">{unit}</span>}
      </p>
    </div>
  );
}

function InsightChip({ text, index }: { text: string; index: number }) {
  const icons = ['🎯', '⏱️', '📈'];
  const borderColors = ['border-violet-500/40', 'border-cyan-500/40', 'border-emerald-500/40'];
  const bgColors = ['bg-violet-500/10', 'bg-cyan-500/10', 'bg-emerald-500/10'];
  const textColors = ['text-violet-200', 'text-cyan-200', 'text-emerald-200'];
  const i = index % 3;
  return (
    <div
      className={`flex items-start gap-3 rounded-xl border ${borderColors[i]} ${bgColors[i]} p-3 ${textColors[i]} text-sm`}
      style={{ animationDelay: `${index * 0.1}s` }}
    >
      <span className="text-base mt-0.5 shrink-0">{icons[i]}</span>
      <span className="leading-snug">{text}</span>
    </div>
  );
}

function BreakdownPie({ breakdown }: { breakdown: ForecastResponse['breakdown'] }) {
  const total = breakdown.baseline + breakdown.influencer_lift_units + breakdown.city_growth_units;
  const data = [
    { name: 'Baseline', value: breakdown.baseline, fill: '#8b5cf6' },
    { name: 'Influencer Uplift', value: breakdown.influencer_lift_units, fill: '#06b6d4' },
    { name: 'City Growth', value: breakdown.city_growth_units, fill: '#10b981' },
  ].filter((d) => d.value > 0);

  return (
    <div className="flex flex-col items-center gap-4">
      <div style={{ width: 220, height: 220 }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={95}
              paddingAngle={3}
              dataKey="value"
              strokeWidth={0}
            >
              {data.map((entry, idx) => (
                <Cell key={idx} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{ background: '#0f1420', border: '1px solid #1e293b', borderRadius: 8 }}
              formatter={(val) => [`${Number(val ?? 0).toFixed(0)} units`, '']}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="w-full space-y-2">
        {data.map((d) => (
          <div key={d.name} className="flex justify-between text-sm items-center">
            <div className="flex items-center gap-2">
              <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ background: d.fill }} />
              <span className="text-slate-300">{d.name}</span>
            </div>
            <div className="text-right">
              <span className="font-mono text-white">{d.value.toFixed(0)}</span>
              <span className="text-slate-500 ml-1 text-xs">({((d.value / total) * 100).toFixed(1)}%)</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function LiftCurveChart({ liftCurve }: { liftCurve: number[] }) {
  const data = HOURS.map((h, i) => ({ hour: h, lift: liftCurve[i] ?? 0 }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
        <defs>
          <linearGradient id="liftGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.5} />
            <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="hour" tick={{ fill: '#64748b', fontSize: 11 }} />
        <YAxis tick={{ fill: '#64748b', fontSize: 11 }} unit="%" />
        <Tooltip
          contentStyle={{ background: '#0f1420', border: '1px solid #1e293b', borderRadius: 8 }}
          formatter={(val) => [`${Number(val ?? 0).toFixed(2)}%`, 'Lift']}
        />
        <Area
          type="monotone"
          dataKey="lift"
          stroke="#8b5cf6"
          strokeWidth={2.5}
          fill="url(#liftGrad)"
          dot={{ fill: '#8b5cf6', strokeWidth: 0, r: 4 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Input form field helpers ────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider">{label}</label>
      {children}
    </div>
  );
}

const inputCls =
  'w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2.5 text-sm text-white placeholder-slate-600 focus:outline-none focus:border-violet-500/50 focus:bg-white/[0.07] transition-all';
const selectCls =
  'w-full rounded-xl border border-white/10 bg-[#0f1420] px-3 py-2.5 text-sm text-white focus:outline-none focus:border-violet-500/50 transition-all appearance-none cursor-pointer';

// ── Main Page ──────────────────────────────────────────────────────────────

export default function DemandForecastPage() {
  const today = new Date().toISOString().slice(0, 10);

  // Form state
  const [productId, setProductId] = useState('SKU-WS-001');
  const [city, setCity] = useState('Mumbai');
  const [date, setDate] = useState(today);
  const [campaignActive, setCampaignActive] = useState(false);
  const [infId, setInfId] = useState('INF-42');
  const [followers, setFollowers] = useState(250000);
  const [engRate, setEngRate] = useState(0.048);
  const [platform, setPlatform] = useState('instagram');

  // Result state
  const [result, setResult] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSuccess, setShowSuccess] = useState(false);

  // Auto-clear success state
  useEffect(() => {
    if (showSuccess) {
      const timer = setTimeout(() => setShowSuccess(false), 2000);
      return () => clearTimeout(timer);
    }
  }, [showSuccess]);

  async function runForecast() {
    setLoading(true);
    setError(null);
    setShowSuccess(false);
    try {
      const body: ForecastRequest = {
        product_id: productId.trim() || 'SKU-001',
        city: city.trim() || 'Mumbai',
        date: date || today,
        campaign_active: campaignActive,
        influencer: campaignActive
          ? {
              id: infId.trim() || null,
              followers: followers || null,
              engagement_rate: engRate || null,
              platform: platform || null,
            }
          : { id: null, followers: null, engagement_rate: null, platform: null },
      };
      const res = await postJson<ForecastResponse>('/api/demand/forecast', body);
      setResult(res);
      setShowSuccess(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Forecast failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen relative" style={{ background: 'linear-gradient(135deg, #0a0e1a 0%, #0f1420 50%, #0c1118 100%)' }}>
      {/* Toast Notification */}
      {showSuccess && (
        <div className="fixed top-6 right-6 z-50 animate-fade-in">
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 backdrop-blur-md px-4 py-3 flex items-center gap-3 shadow-[0_8px_32px_rgba(0,0,0,0.5)]">
            <span className="w-6 h-6 rounded-full bg-emerald-500 flex items-center justify-center text-white text-xs">✓</span>
            <div>
              <p className="text-white text-sm font-semibold">Forecast Updated</p>
              <p className="text-emerald-300/70 text-[10px] uppercase tracking-widest">3-Model Pipeline Complete</p>
            </div>
          </div>
        </div>
      )}

      {/* ── Page header ── */}
      <div className="border-b border-white/5 bg-white/[0.02] backdrop-blur">
        <div className="max-w-7xl mx-auto px-6 py-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs px-2 py-0.5 rounded-full border border-violet-500/40 bg-violet-500/10 text-violet-300 font-medium tracking-wide">
                AGENT · 3-MODEL PIPELINE
              </span>
            </div>
            <h1 className="font-display text-2xl font-bold text-white">
              Demand Forecasting{' '}
              <span className="bg-clip-text text-transparent" style={{ backgroundImage: 'linear-gradient(90deg, #8b5cf6, #06b6d4)' }}>
                Agent
              </span>
            </h1>
            <p className="text-slate-500 text-sm mt-0.5">Real-time predictions · Baseline × Influencer Uplift × City Growth</p>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
              Model 1 — Baseline
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" style={{ animationDelay: '0.3s' }} />
              Model 2 — Uplift
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" style={{ animationDelay: '0.6s' }} />
              Model 3 — City
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8 grid lg:grid-cols-5 gap-8">
        {/* ── LEFT: Input panel ── */}
        <div className="lg:col-span-2 space-y-6">
          <GlowCard>
            <h2 className="text-white font-semibold text-base mb-5 flex items-center gap-2">
              <span className="w-6 h-6 rounded-lg bg-violet-500/20 flex items-center justify-center text-xs text-violet-300">📦</span>
              Product & Location
            </h2>
            <div className="space-y-4">
              <Field label="Product ID">
                <input
                  id="forecast-product-id"
                  className={inputCls}
                  value={productId}
                  onChange={(e) => setProductId(e.target.value)}
                  placeholder="SKU-WS-001"
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="City">
                  <select
                    id="forecast-city"
                    className={selectCls}
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                  >
                    {CITIES.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Date">
                  <input
                    id="forecast-date"
                    type="date"
                    className={inputCls}
                    value={date}
                    onChange={(e) => setDate(e.target.value)}
                  />
                </Field>
              </div>
            </div>
          </GlowCard>

          {/* Campaign toggle */}
          <GlowCard>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-white font-semibold text-base flex items-center gap-2">
                <span className="w-6 h-6 rounded-lg bg-cyan-500/20 flex items-center justify-center text-xs text-cyan-300">📣</span>
                Influencer Campaign
              </h2>
              <button
                id="campaign-toggle"
                type="button"
                onClick={() => setCampaignActive((v) => !v)}
                className={`relative w-12 h-6 rounded-full transition-colors duration-300 ${campaignActive ? 'bg-violet-600' : 'bg-slate-700'}`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-md transition-transform duration-300 ${campaignActive ? 'translate-x-6' : ''}`}
                />
              </button>
            </div>

            {campaignActive ? (
              <div className="space-y-3 animate-fade-in">
                <Field label="Influencer ID">
                  <input
                    id="forecast-inf-id"
                    className={inputCls}
                    value={infId}
                    onChange={(e) => setInfId(e.target.value)}
                    placeholder="INF-42"
                  />
                </Field>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Followers">
                    <input
                      id="forecast-followers"
                      type="number"
                      className={inputCls}
                      value={followers}
                      onChange={(e) => setFollowers(Number(e.target.value))}
                      step={10000}
                      min={1000}
                    />
                  </Field>
                  <Field label="Engagement Rate">
                    <input
                      id="forecast-engagement"
                      type="number"
                      className={inputCls}
                      value={engRate}
                      onChange={(e) => setEngRate(Number(e.target.value))}
                      step={0.001}
                      min={0}
                      max={1}
                      placeholder="0.048"
                    />
                  </Field>
                </div>
                <Field label="Platform">
                  <select
                    id="forecast-platform"
                    className={selectCls}
                    value={platform}
                    onChange={(e) => setPlatform(e.target.value)}
                  >
                    {PLATFORMS.map((p) => (
                      <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>
                    ))}
                  </select>
                </Field>
              </div>
            ) : (
              <p className="text-slate-500 text-sm italic">
                Enable campaign to add influencer uplift via Model 2.
              </p>
            )}
          </GlowCard>

          {/* Run button */}
          <button
            id="run-forecast-btn"
            type="button"
            disabled={loading}
            onClick={() => void runForecast()}
            className="w-full py-3.5 rounded-xl font-semibold text-white text-sm transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed relative overflow-hidden group"
            style={{
              background: loading
                ? 'linear-gradient(135deg, #4c1d95, #0e7490)'
                : 'linear-gradient(135deg, #7c3aed, #0891b2)',
            }}
          >
            <span className="relative z-10 flex items-center justify-center gap-2">
              {loading ? (
                <>
                  <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Running 3-model pipeline…
                </>
              ) : (
                <>
                  <span>⚡</span> Generate Forecast
                </>
              )}
            </span>
            <span className="absolute inset-0 bg-white/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
          </button>

          {error && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 text-red-300 text-sm px-4 py-3">
              {error} — is the backend running on port 8000?
            </div>
          )}
        </div>

        {/* ── RIGHT: Results panel ── */}
        <div className="lg:col-span-3 space-y-6 relative">
          {/* Loading Overlay */}
          {loading && result && (
            <div className="absolute inset-x-0 -inset-y-2 z-40 rounded-2xl bg-[#0a0e1a]/40 backdrop-blur-[2px] flex items-center justify-center animate-fade-in">
              <div className="flex flex-col items-center gap-3">
                <div className="w-10 h-10 border-2 border-violet-500/20 border-t-violet-500 rounded-full animate-spin" />
                <p className="text-violet-300 text-xs font-medium tracking-widest uppercase">Calculating Demand...</p>
              </div>
            </div>
          )}

          {result ? (
            <div className={`space-y-6 transition-all duration-500 ${loading ? 'opacity-30 scale-[0.99] grayscale' : 'opacity-100 scale-100'} ${showSuccess ? 'animate-success-flash' : ''}`}>
              {/* Final demand hero */}
              <GlowCard className="!p-6 text-center relative overflow-hidden">
                <div className="absolute inset-0 rounded-2xl opacity-20" style={{ background: 'radial-gradient(ellipse at 50% 0%, #8b5cf6 0%, transparent 70%)' }} />
                <p className="text-xs uppercase tracking-widest text-slate-500 mb-2 relative">Predicted Final Demand</p>
                <p
                  className="text-7xl font-black font-mono relative mb-1"
                  style={{ backgroundImage: 'linear-gradient(135deg, #a78bfa, #22d3ee)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}
                >
                  {result.final_demand.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                </p>
                <p className="text-slate-400 text-sm relative">units</p>
                {result.uplift.enabled && (
                  <div className="mt-3 relative">
                    <span className="text-xs px-3 py-1 rounded-full bg-violet-500/20 border border-violet-500/30 text-violet-300">
                      +{result.uplift.peak_lift_pct.toFixed(1)}% uplift active
                    </span>
                  </div>
                )}
              </GlowCard>

              {/* KPI grid */}
              <div className="grid grid-cols-3 gap-3">
                <StatBadge label="Baseline" value={result.breakdown.baseline} unit="u" color="violet" />
                <StatBadge label="Lift Units" value={result.breakdown.influencer_lift_units} unit="u" color="cyan" />
                <StatBadge label="City Growth" value={result.breakdown.city_growth_units} unit="u" color="emerald" />
              </div>

              {/* Breakdown + Lift curve */}
              <div className="grid md:grid-cols-2 gap-6">
                <GlowCard>
                  <h3 className="text-white font-semibold text-sm mb-4 flex items-center gap-2">
                    <span className="text-purple-400">◉</span> Demand Breakdown
                  </h3>
                  <BreakdownPie breakdown={result.breakdown} />
                </GlowCard>

                <GlowCard>
                  <h3 className="text-white font-semibold text-sm mb-1 flex items-center gap-2">
                    <span className="text-cyan-400">≈</span> Influencer Lift Curve
                  </h3>
                  <p className="text-slate-500 text-xs mb-3">6h → 96h post-launch (% demand uplift)</p>
                  {result.uplift.enabled ? (
                    <>
                      <LiftCurveChart liftCurve={result.uplift.lift_curve} />
                      <div className="mt-3 flex gap-4 text-xs text-slate-500">
                        <span>λ decay: <strong className="text-slate-300">{result.uplift.decay_lambda.toFixed(4)}</strong></span>
                        <span>Peak: <strong className="text-violet-300">{result.uplift.peak_lift_pct.toFixed(1)}%</strong></span>
                      </div>
                    </>
                  ) : (
                    <div className="flex flex-col items-center justify-center h-40 text-slate-600 text-sm">
                      <span className="text-3xl mb-2 opacity-40">📉</span>
                      No campaign active — lift curve flat.
                    </div>
                  )}
                </GlowCard>
              </div>

              {/* Insights */}
              <GlowCard>
                <h3 className="text-white font-semibold text-sm mb-3 flex items-center gap-2">
                  <span className="text-amber-400">💡</span> AI Insights
                </h3>
                <div className="space-y-2">
                  {result.insights.map((txt, i) => (
                    <InsightChip key={i} text={txt} index={i} />
                  ))}
                </div>
              </GlowCard>

              {/* Raw JSON accordion */}
              <details className="group">
                <summary className="cursor-pointer text-xs text-slate-600 hover:text-slate-400 flex items-center gap-1 transition-colors">
                  <span className="group-open:rotate-90 transition-transform inline-block">▶</span>
                  Raw JSON response
                </summary>
                <pre className="mt-2 rounded-xl bg-black/40 border border-white/5 text-xs text-emerald-400/80 p-4 overflow-x-auto">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </details>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center py-24 text-center gap-4">
              <div
                className="w-20 h-20 rounded-2xl flex items-center justify-center text-4xl"
                style={{ background: 'linear-gradient(135deg, rgba(139,92,246,0.15), rgba(6,182,212,0.15))', border: '1px solid rgba(139,92,246,0.2)' }}
              >
                🤖
              </div>
              <div>
                <p className="text-white font-semibold text-lg">Agent Ready</p>
                <p className="text-slate-500 text-sm mt-1 max-w-xs">
                  Configure your inputs and click{' '}
                  <strong className="text-violet-400">Generate Forecast</strong> to run the three-model pipeline.
                </p>
              </div>
              <div className="grid grid-cols-3 gap-3 mt-4 w-full max-w-md text-xs text-center">
                {[
                  { icon: '📊', label: 'Model 1', desc: 'Baseline demand by product × city × date' },
                  { icon: '📣', label: 'Model 2', desc: 'Influencer lift curve & peak uplift %' },
                  { icon: '🌆', label: 'Model 3', desc: 'City-level growth trend units' },
                ].map((m) => (
                  <div key={m.label} className="rounded-xl border border-white/5 bg-white/[0.03] p-3">
                    <div className="text-2xl mb-1">{m.icon}</div>
                    <div className="text-slate-300 font-medium">{m.label}</div>
                    <div className="text-slate-600 mt-0.5 leading-snug">{m.desc}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
