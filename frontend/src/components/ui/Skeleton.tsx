import type { HTMLAttributes } from 'react';
import { cn } from '../../lib/cn';

export function Skeleton({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      aria-hidden
      className={cn(
        'skeleton-sheen relative overflow-hidden rounded-md bg-surface-sunken',
        className,
      )}
      {...rest}
    />
  );
}

/** Placeholder matching the KPI row so the layout does not shift on load. */
export function SkeletonStatGrid({ count = 4 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="rounded-xl border border-border bg-surface-raised p-5">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="mt-3 h-8 w-16" />
          <Skeleton className="mt-3 h-3 w-full max-w-[12rem]" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonChart({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-xl border border-border bg-surface-raised p-5', className)}>
      <Skeleton className="h-4 w-40" />
      <Skeleton className="mt-1.5 h-3 w-56" />
      <div className="mt-6 flex h-48 items-end gap-2">
        {/* Varied heights read as a chart rather than a generic grey box. */}
        {[45, 70, 35, 85, 55, 95, 40, 75, 60, 88, 50, 68].map((h, i) => (
          <Skeleton key={i} className="flex-1 rounded-sm" style={{ height: `${h}%` }} />
        ))}
      </div>
    </div>
  );
}

export function SkeletonTable({ rows = 6, columns = 6 }: { rows?: number; columns?: number }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-surface-raised">
      <div className="flex gap-4 border-b border-border bg-surface-sunken px-4 py-3">
        {Array.from({ length: columns }, (_, i) => (
          <Skeleton key={i} className="h-3 flex-1" />
        ))}
      </div>
      {Array.from({ length: rows }, (_, r) => (
        <div key={r} className="flex gap-4 border-b border-border/60 px-4 py-3.5 last:border-0">
          {Array.from({ length: columns }, (_, c) => (
            <Skeleton key={c} className="h-3.5 flex-1" />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonPanel({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-xl border border-border bg-surface-raised p-5', className)}>
      <Skeleton className="h-4 w-36" />
      <div className="mt-4 space-y-2.5">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-11/12" />
        <Skeleton className="h-3 w-4/5" />
        <Skeleton className="h-3 w-9/12" />
      </div>
    </div>
  );
}
