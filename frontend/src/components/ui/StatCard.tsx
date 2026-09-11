import type { ReactNode } from 'react';
import { cn } from '../../lib/cn';

export type StatTone = 'neutral' | 'accent' | 'ok' | 'warn' | 'danger' | 'brand';

const ICON_TONES: Record<StatTone, string> = {
  neutral: 'bg-surface-sunken text-content-muted',
  accent: 'bg-accent-soft text-accent',
  ok: 'bg-ok-soft text-ok',
  warn: 'bg-warn-soft text-warn',
  danger: 'bg-danger-soft text-danger',
  brand: 'bg-brand-soft text-brand',
};

const VALUE_TONES: Record<StatTone, string> = {
  neutral: 'text-content',
  accent: 'text-content',
  ok: 'text-content',
  warn: 'text-content',
  danger: 'text-content',
  brand: 'text-content',
};

export interface StatCardProps {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: ReactNode;
  tone?: StatTone;
  className?: string;
}

/**
 * Tone colours the icon chip and not the number itself — a red figure reads as
 * "this value is broken", when what we mean is "this is the stockout metric".
 */
export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = 'neutral',
  className,
}: StatCardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-surface-raised p-5 shadow-xs',
        'transition-colors duration-200 hover:border-border-strong',
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-medium uppercase tracking-wider text-content-subtle">
          {label}
        </p>
        {icon ? (
          <span
            aria-hidden
            className={cn(
              'flex h-7 w-7 shrink-0 items-center justify-center rounded-md',
              '[&>svg]:h-3.5 [&>svg]:w-3.5',
              ICON_TONES[tone],
            )}
          >
            {icon}
          </span>
        ) : null}
      </div>

      <p
        className={cn(
          'mt-2 font-display text-3xl font-semibold tabular-nums',
          VALUE_TONES[tone],
        )}
      >
        {value}
      </p>

      {hint ? (
        <p className="mt-1.5 text-xs leading-relaxed text-content-subtle">{hint}</p>
      ) : null}
    </div>
  );
}
