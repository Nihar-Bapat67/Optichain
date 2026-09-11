/**
 * Chart tokens.
 *
 * These resolve to CSS custom properties rather than literal hex values, and
 * SVG honours `var()` in fill/stroke. The practical effect is that switching
 * theme repaints every chart with no React re-render and no duplicated palette.
 */

export const CHART_COLORS = {
  series1: 'rgb(var(--c-chart-1))',
  series2: 'rgb(var(--c-chart-2))',
  series3: 'rgb(var(--c-chart-3))',
  series4: 'rgb(var(--c-chart-4))',
  series5: 'rgb(var(--c-chart-5))',
  accent: 'rgb(var(--c-accent))',
  brand: 'rgb(var(--c-brand))',
  ok: 'rgb(var(--c-ok))',
  warn: 'rgb(var(--c-warn))',
  danger: 'rgb(var(--c-danger))',
  grid: 'rgb(var(--c-border))',
  axis: 'rgb(var(--c-text-subtle))',
} as const;

/** Ordered palette for series that are coloured by index. */
export const CHART_SERIES = [
  CHART_COLORS.series1,
  CHART_COLORS.series2,
  CHART_COLORS.series3,
  CHART_COLORS.series4,
  CHART_COLORS.series5,
] as const;

export const axisTick = {
  fill: CHART_COLORS.axis,
  fontSize: 11,
} as const;

export const gridProps = {
  strokeDasharray: '3 3',
  stroke: CHART_COLORS.grid,
  vertical: false,
} as const;

/** Muted highlight behind the hovered category — subtle enough not to compete. */
export const cursorProps = {
  fill: 'rgb(var(--c-text) / 0.04)',
} as const;

export const lineCursorProps = {
  stroke: CHART_COLORS.axis,
  strokeWidth: 1,
  strokeDasharray: '4 4',
} as const;
