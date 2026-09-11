import { memo } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Radio } from 'lucide-react';

import { ChartTooltip } from '../../components/charts/ChartTooltip';
import {
  CHART_COLORS,
  axisTick,
  gridProps,
  lineCursorProps,
} from '../../components/charts/chartTheme';
import { EmptyState } from '../../components/ui/States';
import { formatCompact, formatDateShort, formatNumber } from '../../lib/format';
import type { SignalPoint } from '../../types';

export const SignalChart = memo(function SignalChart({ points }: { points: SignalPoint[] }) {
  if (points.length === 0) {
    return (
      <EmptyState
        icon={<Radio />}
        title="No social signal"
        description="No social-type rows for this SKU in the signals table."
        className="h-full"
      />
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
        <defs>
          <linearGradient id="signalGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={CHART_COLORS.series2} stopOpacity={0.35} />
            <stop offset="100%" stopColor={CHART_COLORS.series2} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid {...gridProps} />
        <XAxis
          dataKey="date"
          tick={axisTick}
          tickLine={false}
          axisLine={{ stroke: CHART_COLORS.grid }}
          minTickGap={40}
          tickFormatter={formatDateShort}
        />
        <YAxis
          tick={axisTick}
          tickLine={false}
          axisLine={false}
          width={48}
          tickFormatter={formatCompact}
        />
        <Tooltip
          cursor={lineCursorProps}
          content={
            <ChartTooltip
              labelFormatter={(label) => formatDateShort(String(label))}
              valueFormatter={(value) => formatNumber(value)}
            />
          }
        />
        <Area
          type="monotone"
          dataKey="volume"
          name="Social volume"
          stroke={CHART_COLORS.series2}
          strokeWidth={2}
          fill="url(#signalGradient)"
          activeDot={{ r: 3.5, strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
});
