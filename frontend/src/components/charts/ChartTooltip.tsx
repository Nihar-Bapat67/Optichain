import type { ReactNode } from 'react';

interface TooltipEntry {
  name?: ReactNode;
  value?: number | string | (number | string)[];
  color?: string;
  dataKey?: string | number;
}

export interface ChartTooltipProps {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: ReactNode;
  /** Formats each value; receives the series dataKey for per-series units. */
  valueFormatter?: (value: number, dataKey: string) => string;
  labelFormatter?: (label: ReactNode) => ReactNode;
}

/**
 * Replaces Recharts' `contentStyle` prop, which forced hardcoded hex colours
 * into every chart. A real component picks up theme tokens automatically.
 */
export function ChartTooltip({
  active,
  payload,
  label,
  valueFormatter,
  labelFormatter,
}: ChartTooltipProps) {
  if (!active || !payload?.length) return null;

  const rows = payload.filter((entry) => entry.value !== undefined && entry.value !== null);
  if (!rows.length) return null;

  return (
    <div className="pointer-events-none min-w-[10rem] rounded-lg border border-border bg-surface-overlay px-3 py-2 shadow-lg">
      {label !== undefined && label !== null ? (
        <p className="mb-1.5 border-b border-border pb-1.5 text-2xs font-semibold uppercase tracking-wider text-content-subtle">
          {labelFormatter ? labelFormatter(label) : label}
        </p>
      ) : null}

      <div className="space-y-1">
        {rows.map((entry, index) => {
          const numeric = typeof entry.value === 'number' ? entry.value : Number(entry.value);
          const display =
            valueFormatter && Number.isFinite(numeric)
              ? valueFormatter(numeric, String(entry.dataKey ?? ''))
              : Number.isFinite(numeric)
                ? numeric.toLocaleString(undefined, { maximumFractionDigits: 2 })
                : String(entry.value);

          return (
            <div key={index} className="flex items-center justify-between gap-4 text-xs">
              <span className="flex min-w-0 items-center gap-1.5">
                <span
                  aria-hidden
                  className="h-2 w-2 shrink-0 rounded-full"
                  style={{ background: entry.color }}
                />
                <span className="truncate text-content-muted">{entry.name}</span>
              </span>
              <span className="shrink-0 font-mono tabular-nums font-medium text-content">
                {display}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
