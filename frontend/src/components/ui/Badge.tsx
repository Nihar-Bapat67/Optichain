import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '../../lib/cn';

export type BadgeTone = 'neutral' | 'accent' | 'brand' | 'ok' | 'warn' | 'danger' | 'info';
export type BadgeSize = 'sm' | 'md';

const TONES: Record<BadgeTone, string> = {
  neutral: 'bg-surface-sunken text-content-muted border-border',
  accent: 'bg-accent-soft text-accent border-accent-border',
  brand: 'bg-brand-soft text-brand border-brand-border',
  ok: 'bg-ok-soft text-ok border-ok-border',
  warn: 'bg-warn-soft text-warn border-warn-border',
  danger: 'bg-danger-soft text-danger border-danger-border',
  info: 'bg-info-soft text-info border-info-border',
};

const DOT_TONES: Record<BadgeTone, string> = {
  neutral: 'bg-content-subtle',
  accent: 'bg-accent',
  brand: 'bg-brand',
  ok: 'bg-ok',
  warn: 'bg-warn',
  danger: 'bg-danger',
  info: 'bg-info',
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  size?: BadgeSize;
  /** Leading status dot — for live/state indicators rather than plain labels. */
  dot?: boolean;
  icon?: ReactNode;
}

export function Badge({
  tone = 'neutral',
  size = 'sm',
  dot = false,
  icon,
  className,
  children,
  ...rest
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border font-medium',
        size === 'sm' ? 'px-2 py-0.5 text-2xs' : 'px-2.5 py-1 text-xs',
        TONES[tone],
        className,
      )}
      {...rest}
    >
      {dot ? (
        <span aria-hidden className={cn('h-1.5 w-1.5 shrink-0 rounded-full', DOT_TONES[tone])} />
      ) : null}
      {icon}
      {children}
    </span>
  );
}
