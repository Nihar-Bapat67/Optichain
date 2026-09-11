import type { ReactNode } from 'react';
import { Card, CardBody, CardHeader } from '../ui/Card';
import { Skeleton } from '../ui/Skeleton';
import { InlineError } from '../ui/States';

export interface ChartCardProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  /** Controls (SKU pickers, range toggles) rendered in the header. */
  actions?: ReactNode;
  /** Fixed plot height in px — ResponsiveContainer needs a bounded parent. */
  height: number;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  children: ReactNode;
}

/**
 * Standard frame for every chart on the dashboard: consistent header, and one
 * place that decides how loading and error states look.
 */
export function ChartCard({
  title,
  description,
  icon,
  actions,
  height,
  loading = false,
  error = null,
  onRetry,
  children,
}: ChartCardProps) {
  return (
    <Card className="flex flex-col">
      <CardHeader title={title} description={description} icon={icon} actions={actions} />
      <CardBody className="flex-1">
        {error ? (
          <div style={{ height }} className="flex items-center">
            <InlineError message={error} onRetry={onRetry} className="w-full" />
          </div>
        ) : loading ? (
          <div style={{ height }} className="flex items-end gap-2 px-1 pb-6 pt-2">
            {[52, 74, 41, 88, 60, 96, 45, 78, 63, 90, 55, 71].map((h, i) => (
              <Skeleton key={i} className="flex-1 rounded-sm" style={{ height: `${h}%` }} />
            ))}
          </div>
        ) : (
          <div style={{ height }}>{children}</div>
        )}
      </CardBody>
    </Card>
  );
}
