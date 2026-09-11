import { useMemo } from 'react';
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts';
import { Activity, ChevronRight, Lightbulb, PieChart as PieIcon } from 'lucide-react';

import { ChartTooltip } from '../../components/charts/ChartTooltip';
import {
  CHART_COLORS,
  axisTick,
  gridProps,
  lineCursorProps,
} from '../../components/charts/chartTheme';
import { Badge } from '../../components/ui/Badge';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { formatNumber, formatPercent } from '../../lib/format';
import { LIFT_HOURS } from './constants';
import type { ForecastResponse } from '../../types';

const BREAKDOWN_COLORS = [CHART_COLORS.series1, CHART_COLORS.series2, CHART_COLORS.series3];

function HeroDemand({ result }: { result: ForecastResponse }) {
  return (
    <Card className="relative overflow-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-40 opacity-[0.07]"
        style={{
          background:
            'radial-gradient(ellipse 60% 100% at 50% 0%, rgb(var(--c-accent)) 0%, transparent 70%)',
        }}
      />
      <CardBody className="relative py-8 text-center">
        <p className="text-2xs font-semibold uppercase tracking-widest text-content-subtle">
          Predicted final demand
        </p>
        <p className="mt-2 font-display text-6xl font-semibold tabular-nums text-content">
          {formatNumber(result.final_demand)}
        </p>
        <p className="mt-1 text-sm text-content-subtle">units</p>

        {result.uplift.enabled ? (
          <div className="mt-4 flex justify-center">
            <Badge tone="brand" size="md" dot>
              +{formatPercent(result.uplift.peak_lift_pct)} peak uplift active
            </Badge>
          </div>
        ) : null}
      </CardBody>
    </Card>
  );
}

function ContributionRow({
  label,
  value,
  total,
  color,
}: {
  label: string;
  value: number;
  total: number;
  color: string;
}) {
  const share = total > 0 ? (value / total) * 100 : 0;
  return (
    <div className="flex items-center justify-between gap-4 text-sm">
      <span className="flex min-w-0 items-center gap-2">
        <span
          aria-hidden
          className="h-2.5 w-2.5 shrink-0 rounded-full"
          style={{ background: color }}
        />
        <span className="truncate text-content-muted">{label}</span>
      </span>
      <span className="shrink-0 font-mono tabular-nums">
        <span className="text-content">{formatNumber(value)}</span>
        <span className="ml-1.5 text-xs text-content-subtle">({share.toFixed(1)}%)</span>
      </span>
    </div>
  );
}

function BreakdownCard({ result }: { result: ForecastResponse }) {
  const { baseline, influencer_lift_units, city_growth_units } = result.breakdown;
  const total = baseline + influencer_lift_units + city_growth_units;

  const slices = useMemo(
    () =>
      [
        { name: 'Baseline', value: baseline, fill: BREAKDOWN_COLORS[0] },
        { name: 'Influencer uplift', value: influencer_lift_units, fill: BREAKDOWN_COLORS[1] },
        { name: 'City growth', value: city_growth_units, fill: BREAKDOWN_COLORS[2] },
      ].filter((s) => s.value > 0),
    [baseline, influencer_lift_units, city_growth_units],
  );

  return (
    <Card className="flex flex-col">
      <CardHeader
        title="Demand breakdown"
        description="Contribution of each model to the final figure"
        icon={<PieIcon className="h-3.5 w-3.5" />}
      />
      <CardBody className="flex flex-1 flex-col gap-4">
        <div className="h-48">
          {slices.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  cx="50%"
                  cy="50%"
                  innerRadius={54}
                  outerRadius={82}
                  paddingAngle={2}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {slices.map((slice) => (
                    <Cell key={slice.name} fill={slice.fill} />
                  ))}
                </Pie>
                <Tooltip
                  content={
                    <ChartTooltip valueFormatter={(value) => `${formatNumber(value)} units`} />
                  }
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-content-subtle">
              No positive contributions to chart.
            </div>
          )}
        </div>

        <div className="space-y-2 border-t border-border pt-4">
          <ContributionRow
            label="Baseline"
            value={baseline}
            total={total}
            color={BREAKDOWN_COLORS[0]}
          />
          <ContributionRow
            label="Influencer uplift"
            value={influencer_lift_units}
            total={total}
            color={BREAKDOWN_COLORS[1]}
          />
          <ContributionRow
            label="City growth"
            value={city_growth_units}
            total={total}
            color={BREAKDOWN_COLORS[2]}
          />
        </div>
      </CardBody>
    </Card>
  );
}

function LiftCurveCard({ result }: { result: ForecastResponse }) {
  const data = useMemo(
    () => LIFT_HOURS.map((hour, i) => ({ hour, lift: result.uplift.lift_curve[i] ?? 0 })),
    [result.uplift.lift_curve],
  );

  return (
    <Card className="flex flex-col">
      <CardHeader
        title="Influencer lift curve"
        description="6h → 96h post-launch demand uplift"
        icon={<Activity className="h-3.5 w-3.5" />}
      />
      <CardBody className="flex flex-1 flex-col gap-3">
        {result.uplift.enabled ? (
          <>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
                  <defs>
                    <linearGradient id="liftGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_COLORS.series2} stopOpacity={0.4} />
                      <stop offset="100%" stopColor={CHART_COLORS.series2} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid {...gridProps} />
                  <XAxis
                    dataKey="hour"
                    tick={axisTick}
                    tickLine={false}
                    axisLine={{ stroke: CHART_COLORS.grid }}
                  />
                  <YAxis
                    tick={axisTick}
                    tickLine={false}
                    axisLine={false}
                    width={44}
                    unit="%"
                  />
                  <Tooltip
                    cursor={lineCursorProps}
                    content={
                      <ChartTooltip valueFormatter={(value) => formatPercent(value, 2)} />
                    }
                  />
                  <Area
                    type="monotone"
                    dataKey="lift"
                    name="Lift"
                    stroke={CHART_COLORS.series2}
                    strokeWidth={2.5}
                    fill="url(#liftGradient)"
                    dot={{ fill: CHART_COLORS.series2, strokeWidth: 0, r: 3 }}
                    activeDot={{ r: 4.5, strokeWidth: 0 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <dl className="grid grid-cols-2 gap-3 border-t border-border pt-4">
              <div>
                <dt className="text-2xs uppercase tracking-wider text-content-subtle">
                  Decay λ
                </dt>
                <dd className="mt-0.5 font-mono text-sm tabular-nums text-content">
                  {result.uplift.decay_lambda.toFixed(4)}
                </dd>
              </div>
              <div>
                <dt className="text-2xs uppercase tracking-wider text-content-subtle">
                  Peak lift
                </dt>
                <dd className="mt-0.5 font-mono text-sm tabular-nums text-brand">
                  {formatPercent(result.uplift.peak_lift_pct)}
                </dd>
              </div>
            </dl>
          </>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center py-10 text-center">
            <span
              aria-hidden
              className="flex h-11 w-11 items-center justify-center rounded-lg bg-surface-sunken text-content-subtle"
            >
              <Activity className="h-5 w-5" />
            </span>
            <p className="mt-3 text-sm font-medium text-content">No campaign active</p>
            <p className="mt-1 max-w-xs text-balance text-xs leading-relaxed text-content-subtle">
              Enable an influencer campaign to model the uplift curve and its decay.
            </p>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function InsightsCard({ insights }: { insights: string[] }) {
  if (insights.length === 0) return null;

  return (
    <Card>
      <CardHeader
        title="Model insights"
        description="Narration emitted by the forecast agent"
        icon={<Lightbulb className="h-3.5 w-3.5" />}
      />
      <CardBody>
        <ul className="space-y-2">
          {insights.map((insight, index) => (
            <li
              key={`${index}-${insight}`}
              className="flex items-start gap-2.5 rounded-md border border-border bg-surface-sunken px-3 py-2.5"
            >
              <span
                aria-hidden
                className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: BREAKDOWN_COLORS[index % BREAKDOWN_COLORS.length] }}
              />
              <span className="min-w-0 text-sm leading-relaxed text-content-muted">
                {insight}
              </span>
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

export function ForecastResult({ result }: { result: ForecastResponse }) {
  return (
    <div className="animate-fade-in-up space-y-6">
      <HeroDemand result={result} />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {[
          { label: 'Baseline', value: result.breakdown.baseline, color: BREAKDOWN_COLORS[0] },
          {
            label: 'Lift units',
            value: result.breakdown.influencer_lift_units,
            color: BREAKDOWN_COLORS[1],
          },
          {
            label: 'City growth',
            value: result.breakdown.city_growth_units,
            color: BREAKDOWN_COLORS[2],
          },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl border border-border bg-surface-raised p-4 text-center shadow-xs"
          >
            <p className="text-2xs font-medium uppercase tracking-wider text-content-subtle">
              {stat.label}
            </p>
            <p
              className="mt-1.5 font-display text-2xl font-semibold tabular-nums"
              style={{ color: stat.color }}
            >
              {formatNumber(stat.value, 1)}
            </p>
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <BreakdownCard result={result} />
        <LiftCurveCard result={result} />
      </div>

      <InsightsCard insights={result.insights} />

      <details className="group rounded-xl border border-border bg-surface-raised">
        <summary className="flex cursor-pointer list-none items-center gap-1.5 px-4 py-3 text-xs font-medium text-content-subtle transition-colors hover:text-content">
          <ChevronRight
            aria-hidden
            className="h-3.5 w-3.5 transition-transform group-open:rotate-90"
          />
          Raw JSON response
        </summary>
        <pre className="scrollbar-slim mx-4 mb-4 overflow-x-auto rounded-md border border-border bg-surface px-3 py-2.5 font-mono text-xs leading-relaxed text-content-muted">
          {JSON.stringify(result, null, 2)}
        </pre>
      </details>
    </div>
  );
}
