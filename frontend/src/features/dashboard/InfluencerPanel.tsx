import { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Megaphone } from 'lucide-react';

import { ChartTooltip } from '../../components/charts/ChartTooltip';
import {
  CHART_COLORS,
  axisTick,
  cursorProps,
  gridProps,
} from '../../components/charts/chartTheme';
import { Badge } from '../../components/ui/Badge';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { EmptyState } from '../../components/ui/States';
import { formatNumber } from '../../lib/format';
import type { InfluencerSummary } from '../../types';

interface InfluencerPanelProps {
  summary: InfluencerSummary | null;
  targetsLoaded: number;
}

/** `lift_24h` → `Lift 24h` for axis labels. */
function humanizeTarget(target: string): string {
  return target.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());
}

export function InfluencerPanel({ summary, targetsLoaded }: InfluencerPanelProps) {
  const data = useMemo(() => {
    const targets = summary?.metrics?.targets;
    if (!targets) return [];
    return Object.entries(targets).map(([name, metric]) => ({
      name: humanizeTarget(name),
      rmse: metric.rmse,
      mae: metric.mae,
    }));
  }, [summary]);

  return (
    <Card className="flex h-full flex-col">
      <CardHeader
        title="Influencer model accuracy"
        description="Per-target error for the MODEL2 uplift bundle"
        icon={<Megaphone className="h-3.5 w-3.5" />}
        actions={
          <Badge tone={targetsLoaded > 0 ? 'ok' : 'neutral'} dot>
            {targetsLoaded} loaded
          </Badge>
        }
      />
      <CardBody className="flex min-h-0 flex-1 flex-col">
        {data.length > 0 ? (
          // ResponsiveContainer measures its parent, so that parent needs a
          // resolved height — a bare flex-1 collapses to 0 and Recharts warns.
          <div className="h-[260px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data}
                layout="vertical"
                margin={{ top: 4, right: 12, bottom: 0, left: 8 }}
                barCategoryGap={6}
              >
                <CartesianGrid {...gridProps} horizontal={false} vertical />
                <XAxis type="number" tick={axisTick} tickLine={false} axisLine={false} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={92}
                  tick={axisTick}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  cursor={cursorProps}
                  content={
                    <ChartTooltip valueFormatter={(value) => formatNumber(value, 3)} />
                  }
                />
                <Bar
                  dataKey="rmse"
                  name="RMSE"
                  fill={CHART_COLORS.series1}
                  radius={[0, 3, 3, 0]}
                  maxBarSize={16}
                />
                <Bar
                  dataKey="mae"
                  name="MAE"
                  fill={CHART_COLORS.series2}
                  radius={[0, 3, 3, 0]}
                  maxBarSize={16}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <EmptyState
            icon={<Megaphone />}
            title="No model metrics"
            description={
              <>
                Run the MODEL2 training and ETL steps to generate{' '}
                <code className="rounded bg-surface-sunken px-1 py-0.5 font-mono text-xs text-content-muted">
                  analytics/influencer_metrics.json
                </code>
                .
              </>
            }
            className="flex-1 border-0"
          />
        )}

        {summary?.distribution ? (
          <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-border pt-4">
            <div>
              <dt className="text-2xs uppercase tracking-wider text-content-subtle">
                Actual peak lift
              </dt>
              <dd className="mt-0.5 font-mono text-sm tabular-nums text-content">
                {formatNumber(summary.distribution.peak_lift_pct_actual_mean, 2)}%
              </dd>
            </div>
            <div>
              <dt className="text-2xs uppercase tracking-wider text-content-subtle">
                Predicted peak lift
              </dt>
              <dd className="mt-0.5 font-mono text-sm tabular-nums text-content">
                {formatNumber(summary.distribution.peak_lift_pct_pred_mean, 2)}%
              </dd>
            </div>
          </dl>
        ) : null}
      </CardBody>
    </Card>
  );
}
