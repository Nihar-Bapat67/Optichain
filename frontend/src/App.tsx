import { Suspense, lazy, useCallback, useState } from 'react';
import { RefreshCw } from 'lucide-react';

import { AppShell } from './components/layout/AppShell';
import type { PageKey } from './components/layout/navigation';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Button } from './components/ui/Button';
import { SkeletonPanel, SkeletonStatGrid } from './components/ui/Skeleton';
import { useAsyncData } from './hooks/useAsyncData';
import { fetchJson, isRetryable } from './lib/api';
import type { Health } from './types';

// Split per page so the dashboard's table/chart payload isn't downloaded by
// someone who only opens the forecast agent.
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const ForecastPage = lazy(() => import('./pages/ForecastPage'));

function PageFallback() {
  return (
    <div className="space-y-6">
      <SkeletonStatGrid />
      <div className="grid gap-6 xl:grid-cols-3">
        <SkeletonPanel className="xl:col-span-2" />
        <SkeletonPanel />
      </div>
    </div>
  );
}

// A sleeping free-tier host can take ~60s to answer its first request, so the
// health check retries instead of failing on the first timeout. Local dev
// gives up quickly — there the backend is simply not running.
const WAKE_ATTEMPT_TIMEOUT_MS = 20_000;
const WAKE_BUDGET_MS = import.meta.env.DEV ? 6_000 : 120_000;

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(resolve, ms);
    signal.addEventListener(
      'abort',
      () => {
        window.clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true },
    );
  });
}

export default function App() {
  const [activePage, setActivePage] = useState<PageKey>('dashboard');
  const [refreshToken, setRefreshToken] = useState(0);
  const [wakingSince, setWakingSince] = useState<number | null>(null);

  const health = useAsyncData<Health>(
    async (signal) => {
      const startedAt = Date.now();
      for (let attempt = 1; ; attempt++) {
        try {
          const result = await fetchJson<Health>('/api/health', signal, {
            timeoutMs: WAKE_ATTEMPT_TIMEOUT_MS,
          });
          setWakingSince(null);
          return result;
        } catch (err) {
          const outOfBudget = Date.now() - startedAt > WAKE_BUDGET_MS;
          if (signal.aborted || !isRetryable(err) || outOfBudget) {
            setWakingSince(null);
            throw err;
          }
          setWakingSince(startedAt);
          await sleep(Math.min(5_000, 1_000 * attempt), signal);
        }
      }
    },
    [refreshToken],
  );

  const refreshAll = useCallback(() => setRefreshToken((n) => n + 1), []);

  return (
    <AppShell
      activePage={activePage}
      onNavigate={setActivePage}
      apiOk={health.loading && !health.data ? undefined : (health.data?.ok ?? false)}
      topbarActions={
        activePage === 'dashboard' ? (
          <Button
            size="sm"
            variant="secondary"
            onClick={refreshAll}
            loading={health.loading}
            leadingIcon={<RefreshCw className="h-3.5 w-3.5" />}
          >
            <span className="hidden sm:inline">Refresh</span>
          </Button>
        ) : null
      }
    >
      <ErrorBoundary section={activePage === 'dashboard' ? 'Dashboard' : 'Forecast agent'}>
        <Suspense fallback={<PageFallback />}>
          {activePage === 'dashboard' ? (
            <DashboardPage
              health={health.data}
              healthError={health.error}
              healthLoading={health.initialLoading}
              wakingSince={wakingSince}
              onRetryHealth={refreshAll}
              refreshToken={refreshToken}
            />
          ) : (
            <ForecastPage />
          )}
        </Suspense>
      </ErrorBoundary>
    </AppShell>
  );
}
