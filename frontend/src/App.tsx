import { Suspense, lazy, useCallback, useState } from 'react';
import { RefreshCw } from 'lucide-react';

import { AppShell } from './components/layout/AppShell';
import type { PageKey } from './components/layout/navigation';
import { ErrorBoundary } from './components/ErrorBoundary';
import { Button } from './components/ui/Button';
import { SkeletonPanel, SkeletonStatGrid } from './components/ui/Skeleton';
import { useAsyncData } from './hooks/useAsyncData';
import { fetchJson } from './lib/api';
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

export default function App() {
  const [activePage, setActivePage] = useState<PageKey>('dashboard');
  const [refreshToken, setRefreshToken] = useState(0);

  const health = useAsyncData<Health>(
    (signal) => fetchJson<Health>('/api/health', signal),
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
