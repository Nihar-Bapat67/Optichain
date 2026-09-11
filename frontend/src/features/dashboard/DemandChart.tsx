import { memo, useMemo } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { LineChart as LineChartIcon } from 'lucide-react';

import { ChartTooltip } from '../../components/charts/ChartTooltip';
import { CHART_COLORS, axisTick, gridProps, lineCursorProps } from '../../components/charts/chartTheme';
import { EmptyState } from '../../components/ui/States';
import { formatCompact, formatDateShort, formatNumber } from '../../lib/format';
import type { DemandPoint } from '../../types';

interface DemandChartProps {
  points: DemandPoint[];
}

/**
 * Memoised because the parent re-renders on unrelated state (simulation inputs,
 * filters) and re-rendering a multi-hundred-point chart is not free.
 */
export const DemandChart = memo(function DemandChart({ points }: DemandChartProps) {
  const data = useMemo(
    () =>
      points.map((p) => ({
        date: p.date,
        units_sold: p.units_sold,
        // Recharts skips null but would plot undefined as 0.
        predicted_units: p.predicted_units ?? null,
      })),
    [points],
  );

  if (data.length === 0) {
    return (
      <EmptyState
        icon={<LineChartIcon />}
        title="No demand history"
        description="This SKU has no rows in the demand table yet."
        className="h-full"
      />
    );
  }

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
        <CartesianGrid {...gridProps} />
        <XAxis
          dataKey="date"
          tick={axisTick}
          tickLine={false}
          axisLine={{ stroke: CHART_COLORS.grid }}
          minTickGap={32}
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
              valueFormatter={(value) => `${formatNumber(value)} units`}
            />
          }
        />
        <Legend
          iconType="line"
          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
          formatter={(value) => <span className="text-content-muted">{value}</span>}
        />
        <Line
          type="monotone"
          dataKey="units_sold"
          name="Actual"
          stroke={CHART_COLORS.series3}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 3.5, strokeWidth: 0 }}
        />
        <Line
          type="monotone"
          dataKey="predicted_units"
          name="Predicted"
          stroke={CHART_COLORS.series1}
          strokeWidth={2}
          strokeDasharray="4 3"
          dot={false}
          activeDot={{ r: 3.5, strokeWidth: 0 }}
          connectNulls
        />
      </LineChart>
    </ResponsiveContainer>
  );
});
