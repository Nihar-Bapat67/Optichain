import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { API_ORIGIN } from '../lib/api';
import { EmptyState } from './ui/States';

/** Shown while the health check retries against a host that is spinning up. */
export function WakingState({ startedAt }: { startedAt: number }) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const seconds = Math.max(0, Math.round((now - startedAt) / 1000));
  // Free-tier hosts typically wake in under a minute; cap the bar just short of full.
  const progress = Math.min(95, (seconds / 60) * 100);

  return (
    <EmptyState
      icon={<Loader2 className="animate-spin" />}
      title="Waking up the API"
      description={
        <>
          The backend at <span className="font-mono text-xs">{API_ORIGIN}</span> sleeps when idle and
          takes up to a minute to start. The dashboard loads automatically once it responds.
        </>
      }
    >
      <div className="space-y-2">
        <div
          className="h-1.5 w-full overflow-hidden rounded-full bg-surface-sunken"
          role="progressbar"
          aria-label="API start-up progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress)}
        >
          <div className="h-full rounded-full bg-accent transition-[width] duration-1000" style={{ width: `${progress}%` }} />
        </div>
        <p className="text-2xs tabular-nums text-content-subtle">{seconds}s elapsed</p>
      </div>
    </EmptyState>
  );
}
