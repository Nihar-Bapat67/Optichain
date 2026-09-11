/** @type {import('tailwindcss').Config} */

/**
 * Every colour below resolves to a CSS custom property defined in `src/index.css`.
 * That indirection is what lets a single `class="dark"` on <html> repaint the whole
 * product without a single conditional in component code.
 */
const withAlpha = (variable) => `rgb(var(${variable}) / <alpha-value>)`;

export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['DM Sans', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Outfit', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },

      colors: {
        // ── Surfaces ──────────────────────────────────────────────────────
        canvas: withAlpha('--c-canvas'),
        surface: {
          DEFAULT: withAlpha('--c-surface'),
          raised: withAlpha('--c-surface-raised'),
          overlay: withAlpha('--c-surface-overlay'),
          sunken: withAlpha('--c-surface-sunken'),
          border: withAlpha('--c-border'),
        },
        border: {
          DEFAULT: withAlpha('--c-border'),
          strong: withAlpha('--c-border-strong'),
        },

        // ── Content ───────────────────────────────────────────────────────
        content: {
          DEFAULT: withAlpha('--c-text'),
          muted: withAlpha('--c-text-muted'),
          subtle: withAlpha('--c-text-subtle'),
          inverted: withAlpha('--c-text-inverted'),
        },

        // ── Brand / semantic ──────────────────────────────────────────────
        accent: {
          DEFAULT: withAlpha('--c-accent'),
          hover: withAlpha('--c-accent-hover'),
          soft: withAlpha('--c-accent-soft'),
          border: withAlpha('--c-accent-border'),
          fg: withAlpha('--c-accent-fg'),
        },
        brand: {
          DEFAULT: withAlpha('--c-brand'),
          soft: withAlpha('--c-brand-soft'),
          border: withAlpha('--c-brand-border'),
          fg: withAlpha('--c-brand-fg'),
        },
        danger: {
          DEFAULT: withAlpha('--c-danger'),
          soft: withAlpha('--c-danger-soft'),
          border: withAlpha('--c-danger-border'),
          fg: withAlpha('--c-danger-fg'),
        },
        warn: {
          DEFAULT: withAlpha('--c-warn'),
          soft: withAlpha('--c-warn-soft'),
          border: withAlpha('--c-warn-border'),
          fg: withAlpha('--c-warn-fg'),
        },
        ok: {
          DEFAULT: withAlpha('--c-ok'),
          soft: withAlpha('--c-ok-soft'),
          border: withAlpha('--c-ok-border'),
          fg: withAlpha('--c-ok-fg'),
        },
        info: {
          DEFAULT: withAlpha('--c-info'),
          soft: withAlpha('--c-info-soft'),
          border: withAlpha('--c-info-border'),
          fg: withAlpha('--c-info-fg'),
        },

        // Chart series — stable slots so every visualisation stays consistent.
        chart: {
          1: withAlpha('--c-chart-1'),
          2: withAlpha('--c-chart-2'),
          3: withAlpha('--c-chart-3'),
          4: withAlpha('--c-chart-4'),
          5: withAlpha('--c-chart-5'),
        },
      },

      borderRadius: {
        xs: '0.25rem',
        sm: '0.375rem',
        DEFAULT: '0.5rem',
        md: '0.625rem',
        lg: '0.75rem',
        xl: '1rem',
        '2xl': '1.25rem',
        '3xl': '1.5rem',
      },

      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.02em' }],
        xs: ['0.75rem', { lineHeight: '1.125rem' }],
        sm: ['0.8125rem', { lineHeight: '1.25rem' }],
        base: ['0.875rem', { lineHeight: '1.5rem' }],
        md: ['0.9375rem', { lineHeight: '1.5rem' }],
        lg: ['1.0625rem', { lineHeight: '1.625rem' }],
        xl: ['1.25rem', { lineHeight: '1.75rem', letterSpacing: '-0.011em' }],
        '2xl': ['1.5rem', { lineHeight: '2rem', letterSpacing: '-0.018em' }],
        '3xl': ['1.875rem', { lineHeight: '2.25rem', letterSpacing: '-0.021em' }],
        '4xl': ['2.25rem', { lineHeight: '2.5rem', letterSpacing: '-0.024em' }],
        '5xl': ['3rem', { lineHeight: '1.08', letterSpacing: '-0.028em' }],
        '6xl': ['3.75rem', { lineHeight: '1.05', letterSpacing: '-0.032em' }],
      },

      boxShadow: {
        xs: 'var(--shadow-xs)',
        sm: 'var(--shadow-sm)',
        DEFAULT: 'var(--shadow-md)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
        'focus-ring': '0 0 0 2px rgb(var(--c-canvas)), 0 0 0 4px rgb(var(--c-accent))',
      },

      spacing: {
        4.5: '1.125rem',
        13: '3.25rem',
        15: '3.75rem',
        18: '4.5rem',
        sidebar: '15rem',
        topbar: '3.75rem',
      },

      maxWidth: {
        content: '90rem',
      },

      transitionTimingFunction: {
        out: 'cubic-bezier(0.16, 1, 0.3, 1)',
        'in-out': 'cubic-bezier(0.65, 0, 0.35, 1)',
      },

      keyframes: {
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        'fade-in-up': {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          from: { opacity: '0', transform: 'translateX(16px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'scale-in': {
          from: { opacity: '0', transform: 'scale(0.97)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
      },

      animation: {
        'fade-in': 'fade-in 200ms cubic-bezier(0.16, 1, 0.3, 1) both',
        'fade-in-up': 'fade-in-up 280ms cubic-bezier(0.16, 1, 0.3, 1) both',
        'slide-in-right': 'slide-in-right 260ms cubic-bezier(0.16, 1, 0.3, 1) both',
        'scale-in': 'scale-in 180ms cubic-bezier(0.16, 1, 0.3, 1) both',
      },
    },
  },
  plugins: [],
};
