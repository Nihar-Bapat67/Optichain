/**
 * Shared formatters. Centralised so every number, date and percentage in the
 * product renders the same way.
 */

const compactNumber = new Intl.NumberFormat(undefined, {
  notation: 'compact',
  maximumFractionDigits: 1,
});

export function formatNumber(value: number | null | undefined, fractionDigits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toLocaleString(undefined, {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

/** Compact form for axis ticks and tight cards: 12.4K, 3.1M. */
export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return compactNumber.format(value);
}

export function formatPercent(value: number | null | undefined, fractionDigits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return `${value.toFixed(fractionDigits)}%`;
}

/** Severity arrives as 0–1 from the risk engine and is displayed as a percentage. */
export function formatSeverity(severity: number): string {
  return `${Math.round(severity * 100)}%`;
}

export function formatDateShort(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

/** "3 minutes ago" for freshness indicators. */
export function formatRelativeTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;

  const seconds = Math.round((Date.now() - date.getTime()) / 1000);
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });

  const divisions: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, 'second'],
    [60, 'minute'],
    [24, 'hour'],
    [7, 'day'],
    [4.34524, 'week'],
    [12, 'month'],
    [Number.POSITIVE_INFINITY, 'year'],
  ];

  let duration = seconds;
  for (const [amount, unit] of divisions) {
    if (Math.abs(duration) < amount) return rtf.format(-Math.round(duration), unit);
    duration /= amount;
  }
  return rtf.format(-Math.round(duration), 'year');
}
