import { useCallback, useState } from 'react';
import { Bot, Building2, Megaphone, TrendingUp } from 'lucide-react';

import { ErrorBoundary } from '../components/ErrorBoundary';
import { EmptyState, InlineError } from '../components/ui/States';
import { ForecastForm, type ForecastFormState } from '../features/forecast/ForecastForm';
import { ForecastResult } from '../features/forecast/ForecastResult';
import { postJson, toErrorMessage } from '../lib/api';
import { useToast } from '../providers/toastContext';
import type { ForecastRequest, ForecastResponse } from '../types';

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

const INITIAL_STATE: ForecastFormState = {
  productId: 'SKU-WS-001',
  city: 'Mumbai',
  date: todayIso(),
  campaignActive: false,
  influencerId: 'INF-42',
  followers: 250_000,
  engagementRate: 0.048,
  platform: 'instagram',
};

const MODEL_CARDS = [
  {
    icon: TrendingUp,
    label: 'Model 1',
    description: 'Baseline demand by product, city and date',
  },
  {
    icon: Megaphone,
    label: 'Model 2',
    description: 'Influencer lift curve and peak uplift',
  },
  {
    icon: Building2,
    label: 'Model 3',
    description: 'City-level economic growth units',
  },
];

export default function ForecastPage() {
  const toast = useToast();

  const [form, setForm] = useState<ForecastFormState>(INITIAL_STATE);
  const [result, setResult] = useState<ForecastResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateField = useCallback(
    <K extends keyof ForecastFormState>(key: K, value: ForecastFormState[K]) => {
      setForm((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const runForecast = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Request body matches the original implementation exactly, including the
      // null-filled influencer object when no campaign is active.
      const body: ForecastRequest = {
        product_id: form.productId.trim() || 'SKU-001',
        city: form.city.trim() || 'Mumbai',
        date: form.date || todayIso(),
        campaign_active: form.campaignActive,
        influencer: form.campaignActive
          ? {
              id: form.influencerId.trim() || null,
              followers: form.followers || null,
              engagement_rate: form.engagementRate || null,
              platform: form.platform || null,
            }
          : { id: null, followers: null, engagement_rate: null, platform: null },
      };

      const response = await postJson<ForecastResponse>('/api/demand/forecast', body);
      setResult(response);
      toast.success(
        'Forecast updated',
        `Three-model pipeline complete — ${response.final_demand.toLocaleString()} units predicted.`,
      );
    } catch (err) {
      const message = toErrorMessage(err, 'Forecast failed');
      setError(message);
      toast.error('Forecast failed', message);
    } finally {
      setLoading(false);
    }
  }, [form, toast]);

  return (
    <div className="grid gap-6 xl:grid-cols-5">
      {/* ── Inputs ── */}
      <div className="space-y-5 xl:col-span-2">
        <ForecastForm
          state={form}
          onChange={updateField}
          onSubmit={() => void runForecast()}
          loading={loading}
        />

        {error ? (
          <InlineError
            message={`${error} — confirm the backend is running on port 8000.`}
            onRetry={() => void runForecast()}
          />
        ) : null}
      </div>

      {/* ── Results ── */}
      <div className="relative xl:col-span-3">
        {/* Overlay only when refreshing an existing result, so the previous
            figures stay visible instead of collapsing to a skeleton. */}
        {loading && result ? (
          <div className="absolute inset-0 z-30 flex items-start justify-center rounded-xl bg-canvas/50 pt-24 backdrop-blur-[1px]">
            <div className="flex flex-col items-center gap-3">
              <span
                aria-hidden
                className="h-8 w-8 animate-spin rounded-full border-2 border-accent/25 border-t-accent"
              />
              <p
                role="status"
                className="text-2xs font-medium uppercase tracking-widest text-content-muted"
              >
                Recalculating demand…
              </p>
            </div>
          </div>
        ) : null}

        {result ? (
          <ErrorBoundary section="Forecast results">
            <div className={loading ? 'opacity-50 transition-opacity' : 'transition-opacity'}>
              <ForecastResult result={result} />
            </div>
          </ErrorBoundary>
        ) : (
          <EmptyState
            icon={<Bot />}
            title="Agent ready"
            description="Configure the inputs and generate a forecast to run the three-model pipeline."
            className="h-full"
          >
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {MODEL_CARDS.map(({ icon: Icon, label, description }) => (
                <div
                  key={label}
                  className="rounded-lg border border-border bg-surface px-3 py-3.5 text-center"
                >
                  <Icon aria-hidden className="mx-auto h-4 w-4 text-content-subtle" />
                  <p className="mt-2 text-xs font-medium text-content">{label}</p>
                  <p className="mt-0.5 text-2xs leading-snug text-content-subtle">
                    {description}
                  </p>
                </div>
              ))}
            </div>
          </EmptyState>
        )}
      </div>
    </div>
  );
}
