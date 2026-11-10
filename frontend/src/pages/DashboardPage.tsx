import { useCallback, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowUpRight,
  Boxes,
  Database,
  PackageX,
  Radio,
  ShieldAlert,
  Terminal,
  TrendingUp,
} from 'lucide-react';

import { ChartCard } from '../components/charts/ChartCard';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { WakingState } from '../components/WakingState';
import { Field } from '../components/ui/Field';
import { Select } from '../components/ui/Select';
import { StatCard } from '../components/ui/StatCard';
import { EmptyState, ErrorState } from '../components/ui/States';
import {
  SkeletonChart,
  SkeletonPanel,
  SkeletonStatGrid,
  SkeletonTable,
} from '../components/ui/Skeleton';
import { BriefPanel } from '../features/dashboard/BriefPanel';
import { DemandChart } from '../features/dashboard/DemandChart';
import { InfluencerPanel } from '../features/dashboard/InfluencerPanel';
import { RiskTable } from '../features/dashboard/RiskTable';
import { SignalChart } from '../features/dashboard/SignalChart';
import { SimulationPanel } from '../features/dashboard/SimulationPanel';
import { useAsyncData } from '../hooks/useAsyncData';
import { fetchJson, unreachableHint } from '../lib/api';
import { formatNumber } from '../lib/format';
import type {
  Brief,
  DatasetSummary,
  DemandTimeseries,
  Health,
  InfluencerSummary,
  Kpis,
  RiskResponse,
  SignalTimeseries,
  SkuMetaResponse,
} from '../types';

interface DashboardPageProps {
  health: Health | null;
  healthError: string | null;
  healthLoading: boolean;
  /** Set while the health check is retrying against a host that is starting up. */
  wakingSince: number | null;
  onRetryHealth: () => void;
  /** Bumped by the topbar Refresh button to force a reload of all panels. */
  refreshToken: number;
}

/** Shown when the API is up but the ETL artifacts have not been generated. */
function SetupRequired({ health }: { health: Health | null }) {
  return (
    <EmptyState
      icon={<Terminal />}
      title="Setup required"
      description="The API is reachable, but the analytics tables are missing or incomplete. Generate the artifacts from the notebooks, then run the ETL script from the repository root."
    >
      <div className="space-y-3 text-left">
        <div>
          <p className="mb-1.5 text-2xs font-semibold uppercase tracking-wider text-content-subtle">
            1. Build the case-study tables
          </p>
          <pre className="scrollbar-slim overflow-x-auto rounded-md border border-border bg-surface px-3 py-2 font-mono text-xs text-ok">
            python scripts/build_case_study_tables.py
          </pre>
        </div>
        <div>
          <p className="mb-1.5 text-2xs font-semibold uppercase tracking-wider text-content-subtle">
            2. Start the API from the backend folder
          </p>
          <pre className="scrollbar-slim overflow-x-auto rounded-md border border-border bg-surface px-3 py-2 font-mono text-xs text-ok">
            python -m uvicorn app.main:app --reload --port 8000
          </pre>
        </div>

        {health?.messages?.length ? (
          <div>
            <p className="mb-1.5 text-2xs font-semibold uppercase tracking-wider text-content-subtle">
              Diagnostics
            </p>
            <ul className="space-y-1 rounded-md border border-warn-border bg-warn-soft px-3 py-2">
              {health.messages.slice(0, 8).map((message) => (
                <li key={message} className="flex gap-2 text-xs leading-relaxed text-warn">
                  <span aria-hidden className="mt-1 h-1 w-1 shrink-0 rounded-full bg-warn" />
                  <span className="min-w-0 break-words">{message}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </EmptyState>
  );
}

/** One-line provenance for the numbers on the page. */
function DatasetLine({ summary }: { summary: DatasetSummary | null }) {
  if (!summary?.date_to) return null;
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-content-subtle">
      <Database aria-hidden className="h-3.5 w-3.5" />
      <span>
        History {summary.date_from} → {summary.date_to}
      </span>
      <span aria-hidden>·</span>
      <span>{summary.sku_count} SKUs</span>
      <span aria-hidden>·</span>
      <span>
        Data v{summary.data_version} ({summary.backend})
      </span>
    </p>
  );
}

export default function DashboardPage({
  health,
  healthError,
  healthLoading,
  wakingSince,
  onRetryHealth,
  refreshToken,
}: DashboardPageProps) {
  const [selectedSku, setSelectedSku] = useState('');

  const dataReady = Boolean(
    health?.demand_predictions_present && health?.inventory_present && health?.signals_present,
  );

  // ── Core dashboard payloads ───────────────────────────────────────────────
  const kpis = useAsyncData<Kpis>(
    (signal) => fetchJson<Kpis>('/api/kpis/dashboard', signal),
    [refreshToken],
    { enabled: dataReady },
  );

  const skus = useAsyncData<SkuMetaResponse>(
    (signal) => fetchJson<SkuMetaResponse>('/api/meta/skus', signal),
    [refreshToken],
    { enabled: dataReady },
  );

  const risks = useAsyncData<RiskResponse>(
    (signal) => fetchJson<RiskResponse>('/api/risk/skus', signal),
    [refreshToken],
    { enabled: dataReady },
  );

  const brief = useAsyncData<Brief>(
    (signal) => fetchJson<Brief>('/api/brief/weekly', signal),
    [refreshToken],
    { enabled: dataReady },
  );

  const dataset = useAsyncData<DatasetSummary | null>(
    // Informational only; older backends without this endpoint simply omit the line.
    (signal) => fetchJson<DatasetSummary>('/api/meta/dataset', signal).catch(() => null),
    [refreshToken],
    { enabled: dataReady },
  );

  const influencer = useAsyncData<InfluencerSummary | null>(
    (signal) =>
      // Optional panel: a missing metrics file should not fail the dashboard.
      fetchJson<InfluencerSummary>('/api/influencer/summary', signal).catch(() => null),
    [refreshToken],
    { enabled: dataReady },
  );

  // Derive the active SKU rather than syncing it into state via an effect —
  // that would cause a cascading second render on every metadata load.
  const skuList = useMemo(() => skus.data?.skus ?? [], [skus.data]);
  const activeSku = selectedSku || skuList[0]?.sku_id || '';

  // ── Per-SKU series ────────────────────────────────────────────────────────
  const demandLoader = useCallback(
    (signal: AbortSignal) =>
      fetchJson<DemandTimeseries>(
        `/api/demand/timeseries?sku_id=${encodeURIComponent(activeSku)}`,
        signal,
      ),
    [activeSku],
  );

  const demand = useAsyncData<DemandTimeseries>(demandLoader, [activeSku, refreshToken], {
    enabled: dataReady && Boolean(activeSku),
  });

  const signalsLoader = useCallback(
    (signal: AbortSignal) =>
      fetchJson<SignalTimeseries>(
        // Server-side filter: ~9 KB instead of the SKU's full ~150 KB history.
        `/api/signals/timeseries?sku_id=${encodeURIComponent(activeSku)}&signal_type=social&limit=90`,
        signal,
      ),
    [activeSku],
  );

  const signals = useAsyncData<SignalTimeseries>(signalsLoader, [activeSku, refreshToken], {
    enabled: dataReady && Boolean(activeSku),
  });

  // Matches the original behaviour: social signal only, last 90 points.
  const socialPoints = useMemo(
    () => (signals.data?.points ?? []).filter((p) => p.signal_type === 'social').slice(-90),
    [signals.data],
  );

  const priorityRisks = useMemo(
    () =>
      [...(risks.data?.risks ?? [])]
        .sort((a, b) => b.severity - a.severity)
        .slice(0, 3),
    [risks.data],
  );

  // ── Gate states ───────────────────────────────────────────────────────────
  if (healthLoading && wakingSince !== null) return <WakingState startedAt={wakingSince} />;

  if (healthLoading) {
    return (
      <div className="space-y-6">
        <SkeletonStatGrid />
        <div className="grid gap-6 xl:grid-cols-3">
          <SkeletonChart className="xl:col-span-2" />
          <SkeletonPanel />
        </div>
        <SkeletonTable />
      </div>
    );
  }

  if (healthError) {
    return (
      <ErrorState
        title="Cannot reach the API"
        description={
          import.meta.env.DEV ? (
            <>
              {healthError}. Confirm the backend is running on port 8000 with{' '}
              <code className="rounded bg-surface-sunken px-1 py-0.5 font-mono text-xs">
                python -m uvicorn app.main:app --reload --port 8000
              </code>
              .
            </>
          ) : (
            <>
              {healthError}. {unreachableHint()}
            </>
          )
        }
        onRetry={onRetryHealth}
      />
    );
  }

  if (!dataReady) return <SetupRequired health={health} />;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 border-b border-border pb-5 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-2xs font-semibold uppercase tracking-[0.18em] text-accent">
            Operations intelligence
          </p>
          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-content sm:text-3xl">
            Control tower
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-content-muted">
            A live view of inventory exposure, demand signals, and the decisions that need buyer attention.
          </p>
        </div>
        <DatasetLine summary={dataset.data ?? null} />
      </header>

      {/* ── KPI row ── */}
      {kpis.initialLoading ? (
        <SkeletonStatGrid />
      ) : (
        <section aria-label="Key metrics" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Stockout risk"
            value={formatNumber(kpis.data?.stockout_skus)}
            hint="Demand exceeds cover within the lead-time window"
            icon={<PackageX />}
            tone="danger"
          />
          <StatCard
            label="Overstock risk"
            value={formatNumber(kpis.data?.overstock_skus)}
            hint="High weeks-of-cover against a softening trend"
            icon={<AlertTriangle />}
            tone="warn"
          />
          <StatCard
            label="Signal spikes"
            value={formatNumber(kpis.data?.signal_spikes)}
            hint="Week-over-week social and search intensity upticks"
            icon={<Radio />}
            tone="brand"
          />
          <StatCard
            label="Inventory positions"
            value={formatNumber(kpis.data?.total_inventory_skus)}
            hint="SKU × warehouse combinations tracked"
            icon={<Boxes />}
            tone="accent"
          />
        </section>
      )}

      {priorityRisks.length > 0 ? (
        <section aria-labelledby="priority-actions-heading" className="space-y-3">
          <div className="flex items-end justify-between gap-4">
            <div>
              <h2 id="priority-actions-heading" className="font-display text-lg font-semibold text-content">
                Priority actions
              </h2>
              <p className="mt-0.5 text-sm text-content-subtle">
                Highest-severity positions surfaced from the current risk register.
              </p>
            </div>
            <span className="hidden text-xs text-content-subtle sm:block">Ranked by severity</span>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            {priorityRisks.map((risk) => (
              <div
                key={`${risk.sku_id}-${risk.warehouse_id}-${risk.risk_type}`}
                className="rounded-xl border border-border bg-surface-raised p-4 shadow-xs"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <span
                      aria-hidden
                      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                        risk.risk_type === 'stockout'
                          ? 'bg-danger-soft text-danger'
                          : 'bg-warn-soft text-warn'
                      }`}
                    >
                      {risk.risk_type === 'stockout' ? (
                        <ShieldAlert className="h-4 w-4" />
                      ) : (
                        <AlertTriangle className="h-4 w-4" />
                      )}
                    </span>
                    <div className="min-w-0">
                      <p className="truncate font-mono text-sm font-medium text-content">
                        {risk.sku_id}
                      </p>
                      <p className="text-xs text-content-subtle">{risk.warehouse_id}</p>
                    </div>
                  </div>
                  <ArrowUpRight aria-hidden className="h-4 w-4 shrink-0 text-content-subtle" />
                </div>
                <div className="mt-4 flex items-end justify-between gap-3">
                  <div>
                    <p className="text-2xs font-semibold uppercase tracking-wider text-content-subtle">
                      {risk.risk_type === 'stockout' ? 'Stockout exposure' : 'Overstock exposure'}
                    </p>
                    <p className="mt-1 text-sm text-content-muted">
                      {formatNumber(risk.available_units)} available · {formatNumber(risk.weeks_of_cover, 1)} wks cover
                    </p>
                  </div>
                  <p className="font-mono text-lg font-semibold tabular-nums text-content">
                    {Math.round(risk.severity * 100)}%
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {/* ── Charts + brief ── */}
      <section className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <ChartCard
            title="Demand versus model"
            description="Actual units sold against the stored MODEL1 prediction; hover for daily values"
            icon={<TrendingUp className="h-3.5 w-3.5" />}
            height={288}
            loading={demand.initialLoading}
            error={demand.error}
            onRetry={demand.refresh}
            actions={
              <Field label="SKU" hideLabel className="w-full sm:w-56">
                <Select
                  value={activeSku}
                  onChange={(e) => setSelectedSku(e.target.value)}
                  aria-label="Select SKU"
                  className="h-8 text-xs"
                  options={skuList.map((s) => ({
                    value: s.sku_id,
                    label: `${s.sku_id} — ${s.category}`,
                  }))}
                />
              </Field>
            }
          >
            <DemandChart points={demand.data?.points ?? []} />
          </ChartCard>

          <ChartCard
            title="External social signal"
            description="Last 90 days of social-source volume for the selected SKU"
            icon={<Radio className="h-3.5 w-3.5" />}
            height={224}
            loading={signals.initialLoading}
            error={signals.error}
            onRetry={signals.refresh}
          >
            <SignalChart points={socialPoints} />
          </ChartCard>
        </div>

        <div className="xl:sticky xl:top-[calc(theme(spacing.topbar)+1.5rem)] xl:self-start">
          {brief.initialLoading ? <SkeletonPanel /> : <BriefPanel brief={brief.data} />}
        </div>
      </section>

      {/* ── Risk register ── */}
      <section aria-labelledby="risk-register-heading" className="space-y-3">
        <div>
          <h2
            id="risk-register-heading"
            className="font-display text-lg font-semibold text-content"
          >
            Unified risk register
          </h2>
          <p className="mt-0.5 text-sm text-content-subtle">
            Every SKU × warehouse position flagged by the risk engine, ranked by severity.
          </p>
        </div>

        {risks.initialLoading ? (
          <SkeletonTable />
        ) : risks.error ? (
          <ErrorState description={risks.error} onRetry={risks.refresh} />
        ) : (
          <ErrorBoundary section="Risk register">
            <RiskTable risks={risks.data?.risks ?? []} />
          </ErrorBoundary>
        )}
      </section>

      {/* ── Simulation + influencer models ── */}
      <section className="grid gap-6 lg:grid-cols-2">
        <ErrorBoundary section="Simulation">
          {skus.initialLoading ? (
            <SkeletonPanel />
          ) : (
            <SimulationPanel skus={skuList} defaultSku={activeSku} />
          )}
        </ErrorBoundary>

        <ErrorBoundary section="Influencer models">
          {influencer.initialLoading ? (
            <SkeletonPanel />
          ) : (
            <InfluencerPanel
              summary={influencer.data ?? null}
              targetsLoaded={health?.model2_targets_loaded ?? 0}
            />
          )}
        </ErrorBoundary>
      </section>
    </div>
  );
}
